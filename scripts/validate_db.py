#!/usr/bin/env python3
"""Validate database quality after import."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import EMBEDDINGS_DIR
from app.db import db_session, init_db

POLLUTED_MARKERS = ("Header:", "Specific long description about this code:")
MIN_EMBEDDING_COVERAGE = 0.9
MIN_NLM_SPECIALTY_RATIO = 0.2


def main() -> None:
    init_db()
    errors: list[str] = []

    with db_session() as conn:
        for marker in POLLUTED_MARKERS:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM terms WHERE primary_name LIKE ?",
                (f"%{marker}%",),
            ).fetchone()
            if row["c"] > 0:
                errors.append(f"{row['c']} terms contain '{marker}' in primary_name")

        fts = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='terms_fts'"
        ).fetchone()
        if not fts:
            errors.append("terms_fts table missing — run build_search_index.py")

        terms = conn.execute("SELECT COUNT(*) AS c FROM terms").fetchone()["c"]
        emb = conn.execute("SELECT COUNT(*) AS c FROM term_embeddings").fetchone()["c"]
        if terms > 1000 and emb == 0:
            errors.append("semantic index empty — run build_semantic_index.py or use keyword mode")

        nlm_ro = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM term_translations tt
            JOIN terms t ON t.id = tt.term_id
            WHERE t.code_system = 'NLM' AND tt.locale = 'ro'
            """
        ).fetchone()["c"]
        nlm_terms = conn.execute(
            "SELECT COUNT(*) AS c FROM terms WHERE code_system = 'NLM'"
        ).fetchone()["c"]
        if nlm_terms > 0 and nlm_ro == 0:
            errors.append(
                "no Romanian translations for NLM terms — run translate_curated_ro.py"
            )

        nlm_px_tagged = conn.execute(
            """
            SELECT COUNT(*) AS c FROM terms
            WHERE code_system = 'NLM' AND kind = 'procedure' AND specialty IS NOT NULL
            """
        ).fetchone()["c"]
        nlm_px = conn.execute(
            "SELECT COUNT(*) AS c FROM terms WHERE code_system = 'NLM' AND kind = 'procedure'"
        ).fetchone()["c"]
        if nlm_px > 0:
            ratio = nlm_px_tagged / nlm_px
            if ratio < MIN_NLM_SPECIALTY_RATIO:
                errors.append(
                    f"only {nlm_px_tagged}/{nlm_px} NLM procedures tagged with specialty "
                    f"({ratio:.0%}) — run scripts/backfill_nlm_specialties.py"
                )

        ids_path = EMBEDDINGS_DIR / "term_ids.npy"
        if terms > 1000 and ids_path.exists():
            npy_ids = {int(tid) for tid in np.load(ids_path)}
            db_ids = {int(r["id"]) for r in conn.execute("SELECT id FROM terms").fetchall()}
            stale = npy_ids - db_ids
            if stale:
                errors.append(
                    f"{len(stale)} stale IDs in term_ids.npy — run build_semantic_index.py"
                )
            covered = len(npy_ids & db_ids)
            coverage = covered / len(db_ids) if db_ids else 0.0
            if coverage < MIN_EMBEDDING_COVERAGE:
                errors.append(
                    f"embedding coverage {coverage:.0%} ({covered}/{len(db_ids)}) "
                    f"— run build_semantic_index.py"
                )

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("Validation passed.")


if __name__ == "__main__":
    main()
