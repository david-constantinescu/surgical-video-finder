"""Hybrid keyword + semantic term search."""

from __future__ import annotations

import re
import sqlite3
import struct

import numpy as np

from app.config import EMBEDDINGS_DIR, EMBEDDING_DIM
from app.models import Term

_LAYER_BOOST = {"curated": 1.0, "comprehensive": 0.0}
_SEMANTIC_WEIGHT = 0.55
_FTS_WEIGHT = 0.30
_LAYER_WEIGHT = 0.15

_model = None
_embedding_matrix: np.ndarray | None = None
_term_id_index: dict[int, int] | None = None


def _sanitize_fts_query(q: str) -> str:
    q = q.strip()
    if not q:
        return ""
    tokens = re.findall(r"[\w\u0100-\u024F]+", q, flags=re.UNICODE)
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens[:12])


def _load_embedding_cache() -> tuple[np.ndarray | None, dict[int, int] | None]:
    global _embedding_matrix, _term_id_index
    if _embedding_matrix is not None:
        return _embedding_matrix, _term_id_index

    ids_path = EMBEDDINGS_DIR / "term_ids.npy"
    emb_path = EMBEDDINGS_DIR / "embeddings.npy"
    if not ids_path.exists() or not emb_path.exists():
        return None, None

    term_ids = np.load(ids_path)
    matrix = np.load(emb_path)
    _embedding_matrix = matrix
    _term_id_index = {int(tid): i for i, tid in enumerate(term_ids)}
    return _embedding_matrix, _term_id_index


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from app.config import EMBEDDING_MODEL

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _unpack_embedding(blob: bytes) -> np.ndarray:
    count = len(blob) // 4
    return np.array(struct.unpack(f"{count}f", blob), dtype=np.float32)


def _layer_boost(row: sqlite3.Row) -> float:
    boost = _LAYER_BOOST.get(row["layer"], 0.0)
    if row["is_surgical"]:
        boost = max(boost, 0.5)
    return boost


def _display_name(row: sqlite3.Row, locale: str) -> tuple[str, bool]:
    if locale == "ro" and row["ro_name"]:
        return row["ro_name"], False
    return row["en_name"] or row["primary_name"], locale == "ro" and not row["ro_name"]


def _row_to_term(row: sqlite3.Row, locale: str, score: float | None = None) -> Term:
    display, fallback_en = _display_name(row, locale)
    synonyms = []
    if row["aliases_en"]:
        synonyms.extend(row["aliases_en"].split())
    if locale == "ro" and row["aliases_ro"]:
        synonyms.extend(row["aliases_ro"].split())

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

    name_col = "primary_name_ro" if locale == "ro" else "primary_name_en"
    sql = f"""
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

    results = []
    for hit in hits:
        row = row_map.get(hit["id"])
        if not row:
            continue
        fts_score = 1.0 / (1.0 + max(float(hit["fts_rank"]), 0.0))
        score = _FTS_WEIGHT * fts_score + _LAYER_WEIGHT * _layer_boost(row)
        results.append(_row_to_term(row, locale, score))
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
    matrix, id_index = _load_embedding_cache()
    if matrix is None or id_index is None:
        return _semantic_search_from_db(conn, query, locale, kind, limit)

    model = _get_model()
    q_vec = model.encode([query], normalize_embeddings=True)[0]
    scores = matrix @ q_vec
    top_idx = np.argpartition(-scores, min(limit * 5, len(scores) - 1))[: limit * 5]
    top_idx = top_idx[np.argsort(-scores[top_idx])]

    term_ids = [int(np.load(EMBEDDINGS_DIR / "term_ids.npy")[i]) for i in top_idx]
    if kind:
        filtered = conn.execute(
            f"SELECT id FROM terms WHERE id IN ({','.join('?'*len(term_ids))}) AND kind = ?",
            [*term_ids, kind],
        ).fetchall()
        allowed = {r["id"] for r in filtered}
        term_ids = [tid for tid in term_ids if tid in allowed]

    if not term_ids:
        return []

    placeholders = ",".join("?" * len(term_ids[: limit * 3]))
    rows = conn.execute(
        _base_select() + f" WHERE t.id IN ({placeholders})",
        term_ids[: limit * 3],
    ).fetchall()
    row_map = {r["id"]: r for r in rows}

    results = []
    for tid in term_ids:
        row = row_map.get(tid)
        if not row:
            continue
        idx = id_index[tid]
        sim = float(scores[idx])
        score = _SEMANTIC_WEIGHT * sim + _LAYER_WEIGHT * _layer_boost(row)
        results.append(_row_to_term(row, locale, score))
        if len(results) >= limit:
            break
    return results


def _semantic_search_from_db(
    conn: sqlite3.Connection,
    query: str,
    locale: str,
    kind: str | None,
    limit: int,
) -> list[Term]:
    model = _get_model()
    q_vec = model.encode([query], normalize_embeddings=True)[0]

    sql = "SELECT term_id, embedding FROM term_embeddings"
    rows = conn.execute(sql).fetchall()
    scored = []
    for row in rows:
        vec = _unpack_embedding(row["embedding"])
        sim = float(np.dot(vec, q_vec))
        scored.append((row["term_id"], sim))
    scored.sort(key=lambda x: -x[1])
    term_ids = [tid for tid, _ in scored[: limit * 5]]

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

    placeholders = ",".join("?" * len(term_ids[:limit]))
    detail_rows = conn.execute(
        _base_select() + f" WHERE t.id IN ({placeholders})",
        term_ids[:limit],
    ).fetchall()
    sim_map = dict(scored)
    return [
        _row_to_term(
            r,
            locale,
            _SEMANTIC_WEIGHT * sim_map.get(r["id"], 0) + _LAYER_WEIGHT * _layer_boost(r),
        )
        for r in detail_rows
    ]


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    locale: str = "en",
    kind: str | None = None,
    limit: int = 20,
) -> list[Term]:
    kw = keyword_search(conn, query, locale, kind, limit)
    sem = semantic_search(conn, query, locale, kind, limit)

    merged: dict[int, Term] = {}
    for term in kw + sem:
        if term.id in merged:
            merged[term.id].score = (merged[term.id].score or 0) + (term.score or 0)
        else:
            merged[term.id] = term

    ranked = sorted(merged.values(), key=lambda t: -(t.score or 0))
    return ranked[:limit]


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
