"""Hybrid keyword + semantic term search."""

from __future__ import annotations

import re
import sqlite3
import threading
import unicodedata

import numpy as np

from app.config import EMBEDDINGS_DIR, RRF_K
from app.models import Term

_RO_LOCALE_SYSTEMS = frozenset({"ACHI-RO", "ICD-10-AM-RO"})
_FTS_NAME_COLS = {"en": "primary_name_en", "ro": "primary_name_ro"}

_model = None
_model_lock = threading.Lock()
_embedding_matrix: np.ndarray | None = None
_term_id_index: dict[int, int] | None = None
_term_ids_array: np.ndarray | None = None


class SemanticIndexNotReady(Exception):
    """Raised when semantic search is requested but embeddings are missing."""


def _strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _sanitize_fts_query(q: str) -> str:
    q = _strip_diacritics(q.strip())
    if not q:
        return ""
    tokens = re.findall(r"[\w]+", q, flags=re.UNICODE)
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens[:12])


def _bm25_to_score(rank: float) -> float:
    # SQLite FTS5 bm25: lower (more negative) = better match
    return max(0.0, -float(rank))


def _load_embedding_cache() -> tuple[np.ndarray | None, dict[int, int] | None, np.ndarray | None]:
    global _embedding_matrix, _term_id_index, _term_ids_array
    if _embedding_matrix is not None:
        return _embedding_matrix, _term_id_index, _term_ids_array

    ids_path = EMBEDDINGS_DIR / "term_ids.npy"
    emb_path = EMBEDDINGS_DIR / "embeddings.npy"
    if not ids_path.exists() or not emb_path.exists():
        return None, None, None

    term_ids = np.load(ids_path)
    matrix = np.load(emb_path)
    _embedding_matrix = matrix
    _term_ids_array = term_ids
    _term_id_index = {int(tid): i for i, tid in enumerate(term_ids)}
    return _embedding_matrix, _term_id_index, _term_ids_array


def semantic_index_ready(conn: sqlite3.Connection | None = None) -> bool:
    matrix, id_index, _ = _load_embedding_cache()
    if matrix is not None and id_index:
        return True
    if conn is None:
        return False
    row = conn.execute("SELECT COUNT(*) AS c FROM term_embeddings").fetchone()
    return row["c"] > 0


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            from app.config import EMBEDDING_MODEL

            _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _layer_boost(row: sqlite3.Row) -> float:
    boost = 1.0 if row["layer"] == "curated" else 0.0
    if row["is_surgical"]:
        boost = max(boost, 0.5)
    return boost


def _exact_match_bonus(query: str, row: sqlite3.Row, locale: str) -> float:
    q = query.strip().lower()
    if not q:
        return 0.0
    names = [
        (row["en_name"] or "").lower(),
        (row["ro_name"] or "").lower(),
        (row["primary_name"] or "").lower(),
        (row["code"] or "").lower(),
    ]
    for name in names:
        if not name:
            continue
        if name == q:
            return 0.5
        if name.startswith(q) or q in name.split():
            return 0.25
    return 0.0


def _display_name(row: sqlite3.Row, locale: str) -> tuple[str, bool, bool]:
    en_name = row["en_name"]
    ro_name = row["ro_name"]
    code_system = row["code_system"] or ""

    if locale == "ro":
        if ro_name:
            return ro_name, False, False
        if en_name:
            return en_name, True, False
        return row["primary_name"], True, False

    if en_name and code_system not in _RO_LOCALE_SYSTEMS:
        return en_name, False, False
    if en_name and en_name != row["primary_name"]:
        return en_name, False, False
    if code_system in _RO_LOCALE_SYSTEMS or (ro_name and not en_name):
        name = ro_name or row["primary_name"]
        return name, False, True
    return en_name or row["primary_name"], False, False


def _video_query(display: str, row: sqlite3.Row, locale: str, fallback_ro: bool) -> str:
    if locale == "en" and fallback_ro:
        if row["code"]:
            return str(row["code"])
        return _strip_diacritics(display)
    return display


def _row_to_term(
    row: sqlite3.Row,
    locale: str,
    score: float | None = None,
    query: str = "",
) -> Term:
    display, fallback_en, fallback_ro = _display_name(row, locale)
    synonyms = []
    if row["aliases_en"]:
        synonyms.extend(row["aliases_en"].split())
    if locale == "ro" and row["aliases_ro"]:
        synonyms.extend(row["aliases_ro"].split())

    if score is not None and query:
        score = min(1.0, score + _exact_match_bonus(query, row, locale))

    return Term(
        id=row["id"],
        kind=row["kind"],
        code=row["code"],
        code_system=row["code_system"],
        primary_name=row["primary_name"],
        consumer_name=row["consumer_name"],
        layer=row["layer"],
        specialty=row["specialty"],
        is_surgical=bool(row["is_surgical"]),
        complexity=row["complexity"],
        display_name=display,
        locale=locale,
        synonyms=synonyms[:20],
        score=score,
        fallback_en=fallback_en,
        fallback_ro=fallback_ro,
        video_query=_video_query(display, row, locale, fallback_ro),
    )


def _base_select() -> str:
    return """
        SELECT
          t.id, t.kind, t.code, t.code_system, t.primary_name, t.consumer_name,
          t.layer, t.specialty, t.is_surgical, t.complexity,
          COALESCE(en.primary_name, t.primary_name) AS en_name,
          en.consumer_name AS en_consumer,
          ro.primary_name AS ro_name,
          ro.consumer_name AS ro_consumer,
          (
            SELECT GROUP_CONCAT(s.alias, ' ')
            FROM synonyms s WHERE s.term_id = t.id AND s.locale = 'en'
          ) AS aliases_en,
          (
            SELECT GROUP_CONCAT(s.alias, ' ')
            FROM synonyms s WHERE s.term_id = t.id AND s.locale = 'ro'
          ) AS aliases_ro
        FROM terms t
        LEFT JOIN term_translations en ON en.term_id = t.id AND en.locale = 'en'
        LEFT JOIN term_translations ro ON ro.term_id = t.id AND ro.locale = 'ro'
    """


def keyword_search(
    conn: sqlite3.Connection,
    query: str,
    locale: str = "en",
    kind: str | None = None,
    limit: int = 20,
) -> list[Term]:
    fts_q = _sanitize_fts_query(query)
    if not fts_q:
        return []

    name_col = _FTS_NAME_COLS.get(locale, "primary_name_en")
    sql = """
        SELECT t.id, bm25(terms_fts) AS fts_rank
        FROM terms_fts
        JOIN terms t ON t.id = terms_fts.term_id
        WHERE terms_fts MATCH ?
    """
    params: list = [fts_q]
    if kind:
        sql += " AND t.kind = ?"
        params.append(kind)
    sql += f" ORDER BY bm25(terms_fts), {name_col} LIMIT ?"
    params.append(limit * 3)

    try:
        hits = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []

    if not hits:
        return []

    ids = [h["id"] for h in hits]
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        _base_select() + f" WHERE t.id IN ({placeholders})",
        ids,
    ).fetchall()
    row_map = {r["id"]: r for r in rows}

    results: list[Term] = []
    for hit in hits:
        row = row_map.get(hit["id"])
        if not row:
            continue
        fts_score = _bm25_to_score(hit["fts_rank"])
        layer = _layer_boost(row) * 0.1
        score = min(1.0, fts_score + layer + _exact_match_bonus(query, row, locale))
        results.append(_row_to_term(row, locale, score, query))
        if len(results) >= limit:
            break
    return results


def semantic_search(
    conn: sqlite3.Connection,
    query: str,
    locale: str = "en",
    kind: str | None = None,
    limit: int = 20,
) -> list[Term]:
    matrix, id_index, term_ids_arr = _load_embedding_cache()
    if matrix is None or id_index is None or term_ids_arr is None:
        if not semantic_index_ready(conn):
            raise SemanticIndexNotReady(
                "Semantic index not built. Run: python scripts/build_semantic_index.py"
            )
        return []

    model = _get_model()
    q_vec = model.encode([query], normalize_embeddings=True)[0]
    scores = matrix @ q_vec
    top_n = min(limit * 5, len(scores))
    top_idx = np.argpartition(-scores, top_n - 1)[:top_n]

    candidates: list[tuple[int, float]] = []
    for idx in top_idx:
        tid = int(term_ids_arr[idx])
        sim = float(scores[idx])
        layer = 0.0
        candidates.append((tid, sim))

    candidates.sort(key=lambda x: -x[1])
    term_ids = [tid for tid, _ in candidates]

    if kind and term_ids:
        placeholders = ",".join("?" * len(term_ids))
        allowed = {
            r["id"]
            for r in conn.execute(
                f"SELECT id FROM terms WHERE id IN ({placeholders}) AND kind = ?",
                [*term_ids, kind],
            ).fetchall()
        }
        term_ids = [tid for tid in term_ids if tid in allowed]

    if not term_ids:
        return []

    sim_map = dict(candidates)
    placeholders = ",".join("?" * len(term_ids[: limit * 3]))
    rows = conn.execute(
        _base_select() + f" WHERE t.id IN ({placeholders})",
        term_ids[: limit * 3],
    ).fetchall()
    row_map = {r["id"]: r for r in rows}

    scored_terms: list[tuple[float, Term]] = []
    for tid in term_ids:
        row = row_map.get(tid)
        if not row:
            continue
        sim = sim_map[tid]
        layer = _layer_boost(row) * 0.1
        score = min(1.0, sim + layer + _exact_match_bonus(query, row, locale))
        scored_terms.append((score, _row_to_term(row, locale, score, query)))
        if len(scored_terms) >= limit:
            break

    scored_terms.sort(key=lambda x: -x[0])
    return [t for _, t in scored_terms[:limit]]


def _rrf_merge(
    kw: list[Term],
    sem: list[Term],
    query: str,
    locale: str,
    limit: int,
) -> list[Term]:
    rrf_scores: dict[int, float] = {}
    term_map: dict[int, Term] = {}

    for rank, term in enumerate(kw):
        rrf_scores[term.id] = rrf_scores.get(term.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        term_map[term.id] = term

    for rank, term in enumerate(sem):
        rrf_scores[term.id] = rrf_scores.get(term.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        if term.id not in term_map:
            term_map[term.id] = term

    ranked_ids = sorted(rrf_scores.keys(), key=lambda i: -rrf_scores[i])
    results: list[Term] = []
    for tid in ranked_ids[:limit]:
        term = term_map[tid]
        term.score = min(1.0, rrf_scores[tid])
        results.append(term)
    return results


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    locale: str = "en",
    kind: str | None = None,
    limit: int = 20,
) -> list[Term]:
    kw = keyword_search(conn, query, locale, kind, limit)
    try:
        sem = semantic_search(conn, query, locale, kind, limit)
    except SemanticIndexNotReady:
        sem = []
    if not sem:
        return kw
    if not kw:
        return sem
    return _rrf_merge(kw, sem, query, locale, limit)


def search_terms(
    conn: sqlite3.Connection,
    query: str,
    locale: str = "en",
    kind: str | None = None,
    mode: str = "hybrid",
    limit: int = 20,
) -> list[Term]:
    if not query.strip():
        return []
    if mode == "keyword":
        return keyword_search(conn, query, locale, kind, limit)
    if mode == "semantic":
        return semantic_search(conn, query, locale, kind, limit)
    return hybrid_search(conn, query, locale, kind, limit)


def get_term(conn: sqlite3.Connection, term_id: int, locale: str = "en") -> Term | None:
    row = conn.execute(_base_select() + " WHERE t.id = ?", (term_id,)).fetchone()
    if not row:
        return None
    return _row_to_term(row, locale)


def get_terms_batch(conn: sqlite3.Connection, term_ids: list[int], locale: str = "en") -> list[Term]:
    if not term_ids:
        return []
    placeholders = ",".join("?" * len(term_ids))
    rows = conn.execute(
        _base_select() + f" WHERE t.id IN ({placeholders})",
        term_ids,
    ).fetchall()
    return [_row_to_term(r, locale) for r in rows]
