#!/usr/bin/env python3
"""Build multilingual semantic embeddings for all terms."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import EMBEDDING_DIM, EMBEDDING_MODEL, EMBEDDINGS_DIR
from app.db import db_session, embedding_model_name, init_db, log_import

BATCH_SIZE = 64


def pack_embedding(vec: np.ndarray) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec.astype(np.float32))


def build_document(row) -> str:
    parts = [
        row["en_name"] or "",
        row["en_consumer"] or "",
        row["aliases_en"] or "",
        row["ro_name"] or "",
        row["ro_consumer"] or "",
        row["aliases_ro"] or "",
        row["code"] or "",
        row["kind"] or "",
        row["specialty"] or "",
    ]
    return " ".join(p for p in parts if p).strip()


def main() -> None:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit("Install sentence-transformers: pip install sentence-transformers") from exc

    init_db()
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT
              t.id, t.code, t.kind, t.specialty,
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
            ORDER BY t.id
            """
        ).fetchall()

    if not rows:
        print("No terms to embed; run import scripts first.")
        return

    print(f"Loading model {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    docs = [build_document(r) for r in rows]
    term_ids = [r["id"] for r in rows]

    print(f"Encoding {len(docs)} terms...")
    embeddings = model.encode(
        docs,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    matrix = np.array(embeddings, dtype=np.float32)
    np.save(EMBEDDINGS_DIR / "term_ids.npy", np.array(term_ids, dtype=np.int32))
    np.save(EMBEDDINGS_DIR / "embeddings.npy", matrix)

    model_name = embedding_model_name()
    with db_session() as conn:
        conn.execute("DELETE FROM term_embeddings")
        for tid, vec in zip(term_ids, matrix):
            conn.execute(
                "INSERT INTO term_embeddings (term_id, model, embedding) VALUES (?, ?, ?)",
                (tid, model_name, pack_embedding(vec)),
            )
        log_import(conn, "term_embeddings", model_name, len(term_ids))

    print(f"Stored {len(term_ids)} embeddings ({EMBEDDING_DIM}-dim) in DB and numpy cache.")


if __name__ == "__main__":
    main()
