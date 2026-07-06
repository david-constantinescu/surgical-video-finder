"""Flask server for Surgical Video Finder."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from app.config import DB_PATH, DEFAULT_LOCALE, FLASK_DEBUG, FLASK_PORT, SUPPORTED_LOCALES
from app.db import db_session, init_db
from app.search import get_term, get_terms_batch, search_terms
from app.video_links import build_video_links

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


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    init_db()

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
        limit = min(int(request.args.get("limit", 20)), 50)

        if not q:
            return jsonify({"results": [], "query": q, "lang": lang})

        with db_session() as conn:
            results = search_terms(conn, q, lang, kind or None, mode, limit)

        return jsonify({
            "results": [term_to_dict(t, lang) for t in results],
            "query": q,
            "lang": lang,
            "mode": mode,
        })

    @app.get("/api/terms/<int:term_id>")
    def api_term(term_id: int):
        lang = resolve_locale()
        with db_session() as conn:
            term = get_term(conn, term_id, lang)
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

        with db_session() as conn:
            terms = get_terms_batch(conn, [int(i) for i in ids], lang)
        return jsonify({"terms": [term_to_dict(t, lang) for t in terms], "lang": lang})

    @app.get("/api/videos/links")
    def api_video_links():
        lang = resolve_locale()
        raw_ids = request.args.get("term_ids", "")
        ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        if not ids:
            return jsonify({"terms": [], "sources": [], "lang": lang})

        with db_session() as conn:
            terms = get_terms_batch(conn, ids, lang)
            links = build_video_links(conn, terms, lang)

        return jsonify({
            "terms": [term_to_dict(t, lang) for t in terms],
            "sources": [asdict(link) for link in links],
            "lang": lang,
        })

    @app.get("/api/health")
    def health():
        exists = DB_PATH.exists()
        with db_session() as conn:
            term_count = conn.execute("SELECT COUNT(*) AS c FROM terms").fetchone()["c"]
            source_count = conn.execute("SELECT COUNT(*) AS c FROM video_sources").fetchone()["c"]
        return jsonify({
            "status": "ok",
            "db": exists,
            "terms": term_count,
            "video_sources": source_count,
        })

    return app


def term_to_dict(term, lang: str) -> dict:
    fallback_en = lang == "ro" and term.display_name == (term.primary_name or "")
    return {
        "id": term.id,
        "kind": term.kind,
        "code": term.code,
        "code_system": term.code_system,
        "primary_name": term.primary_name,
        "consumer_name": term.consumer_name,
        "display_name": term.display_name,
        "layer": term.layer,
        "specialty": term.specialty,
        "is_surgical": term.is_surgical,
        "complexity": term.complexity,
        "synonyms": term.synonyms,
        "score": term.score,
        "locale": lang,
        "fallback_en": fallback_en,
    }


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)
