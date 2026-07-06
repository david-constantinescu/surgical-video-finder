"""Flask server for Surgical Video Finder."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

from app import config
from app.config import DEFAULT_LOCALE, FLASK_DEBUG, FLASK_HOST, FLASK_PORT, SUPPORTED_LOCALES
from app.db import db_read_session, init_db
from app.inline_videos import (
    enrich_groups_with_inline_videos,
    inline_api_status,
)
from app.search import SemanticIndexNotReady, get_term, get_terms_batch, search_terms
from app.video_links import build_video_link_groups

I18N_DIR = Path(__file__).parent / "i18n"
_bundles: dict[str, dict] = {}


def load_i18n(lang: str) -> dict:
    if lang not in _bundles:
        path = I18N_DIR / f"{lang}.json"
        _bundles[lang] = json.loads(path.read_text(encoding="utf-8"))
    return _bundles[lang]


def resolve_locale() -> str:
    lang = request.args.get("lang") or request.headers.get("Accept-Language", DEFAULT_LOCALE)[:2]
    return lang if lang in SUPPORTED_LOCALES else DEFAULT_LOCALE


def parse_int_param(value: str | None, default: int, *, name: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"invalid {name}") from exc


def parse_id_list(values: list) -> list[int]:
    ids: list[int] = []
    for raw in values:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError) as exc:
            raise ValueError("ids must be integers") from exc
    return ids


def _prewarm_semantic_background() -> None:
    """Load embedding cache + model in a daemon thread so first semantic query is fast."""

    def _run() -> None:
        try:
            from app.search import _get_model, _load_embedding_cache

            matrix, _, _ = _load_embedding_cache()
            if matrix is not None:
                _get_model()
        except Exception:
            pass  # keyword-only installs skip semantic assets

    threading.Thread(target=_run, daemon=True, name="semantic-prewarm").start()


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    init_db()
    _prewarm_semantic_background()

    @app.before_request
    def open_db():
        g._db_cm = db_read_session()
        g.db = g._db_cm.__enter__()

    @app.teardown_request
    def close_db(exc):
        cm = g.pop("_db_cm", None)
        if cm is not None:
            cm.__exit__(None, None, None)

    @app.get("/")
    def index():
        lang = resolve_locale()
        return render_template("index.html", lang=lang)

    @app.get("/api/i18n/<lang>")
    def api_i18n(lang: str):
        if lang not in SUPPORTED_LOCALES:
            lang = DEFAULT_LOCALE
        return jsonify(load_i18n(lang))

    @app.get("/api/terms/search")
    def api_search():
        q = request.args.get("q", "").strip()
        lang = resolve_locale()
        kind = request.args.get("kind")
        mode = request.args.get("mode", "hybrid")
        try:
            limit = min(parse_int_param(request.args.get("limit"), 20, name="limit"), 50)
        except ValueError:
            return jsonify({"error": "invalid limit"}), 400

        if not q:
            return jsonify({"results": [], "query": q, "lang": lang, "count": 0})

        try:
            results = search_terms(g.db, q, lang, kind or None, mode, limit)
        except SemanticIndexNotReady as exc:
            return jsonify({"error": "semantic_index_missing", "message": str(exc)}), 503

        return jsonify({
            "results": [term_to_dict(t, lang) for t in results],
            "query": q,
            "lang": lang,
            "mode": mode,
            "count": len(results),
        })

    @app.get("/api/terms/<int:term_id>")
    def api_term(term_id: int):
        lang = resolve_locale()
        term = get_term(g.db, term_id, lang)
        if not term:
            return jsonify({"error": "not_found"}), 404
        return jsonify(term_to_dict(term, lang))

    @app.post("/api/terms/batch")
    def api_batch():
        payload = request.get_json(silent=True) or {}
        ids = payload.get("ids") or []
        lang = payload.get("lang") or resolve_locale()
        if not isinstance(ids, list):
            return jsonify({"error": "ids must be a list"}), 400
        try:
            id_list = parse_id_list(ids)
        except ValueError:
            return jsonify({"error": "ids must be integers"}), 400

        terms = get_terms_batch(g.db, id_list, lang)
        return jsonify({"terms": [term_to_dict(t, lang) for t in terms], "lang": lang})

    @app.get("/api/videos/links")
    def api_video_links():
        lang = resolve_locale()
        raw_ids = request.args.get("term_ids", "")
        try:
            ids = parse_id_list([x for x in raw_ids.split(",") if x.strip()])
        except ValueError:
            return jsonify({"error": "term_ids must be integers"}), 400
        if not ids:
            return jsonify({"terms": [], "groups": [], "sources": [], "lang": lang})

        terms = get_terms_batch(g.db, ids, lang)
        groups = build_video_link_groups(g.db, terms, lang)
        if request.args.get("inline", "1") != "0":
            enrich_groups_with_inline_videos(
                g.db,
                groups,
                terms,
                lang,
                force_refresh=request.args.get("refresh") == "1",
            )
        flat = [link for g in groups for link in g.sources]

        return jsonify({
            "terms": [term_to_dict(t, lang) for t in terms],
            "groups": [
                {
                    "term_id": grp.term_id,
                    "term_name": grp.term_name,
                    "inline_videos": [asdict(v) for v in grp.inline_videos],
                    "sources": [asdict(s) for s in grp.sources],
                }
                for grp in groups
            ],
            "sources": [asdict(link) for link in flat],
            "lang": lang,
            "inline_apis": inline_api_status(),
            "youtube_api": inline_api_status()["youtube"],
        })

    @app.get("/api/sources")
    def api_sources():
        rows = g.db.execute(
            "SELECT slug, name, tier, language, specialty, requires_auth FROM video_sources ORDER BY name"
        ).fetchall()
        return jsonify({"sources": [dict(r) for r in rows]})

    @app.get("/api/health")
    def health():
        if not config.DB_PATH.exists():
            return jsonify({
                "status": "no_database",
                "db": False,
                "terms": 0,
                "video_sources": 0,
                "message": "Run python scripts/build_all.py",
            }), 503
        try:
            term_count = g.db.execute("SELECT COUNT(*) AS c FROM terms").fetchone()["c"]
            source_count = g.db.execute("SELECT COUNT(*) AS c FROM video_sources").fetchone()["c"]
        except Exception:
            return jsonify({"status": "error", "db": True, "message": "database unreadable"}), 500
        if term_count == 0:
            return jsonify({
                "status": "empty_database",
                "db": True,
                "terms": 0,
                "video_sources": source_count,
                "message": "Run python scripts/build_all.py",
            }), 503
        return jsonify({
            "status": "ok",
            "db": True,
            "terms": term_count,
            "video_sources": source_count,
            "inline_apis": inline_api_status(),
            "youtube_api": inline_api_status()["youtube"],
        })

    return app


def term_to_dict(term, lang: str) -> dict:
    return {
        "id": term.id,
        "kind": term.kind,
        "code": term.code,
        "code_system": term.code_system,
        "primary_name": term.primary_name,
        "consumer_name": term.consumer_name,
        "display_name": term.display_name,
        "video_query": term.video_query,
        "layer": term.layer,
        "specialty": term.specialty,
        "is_surgical": term.is_surgical,
        "complexity": term.complexity,
        "synonyms": term.synonyms,
        "score": term.score,
        "locale": lang,
        "fallback_en": term.fallback_en,
        "fallback_ro": term.fallback_ro,
    }


app = create_app()


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
