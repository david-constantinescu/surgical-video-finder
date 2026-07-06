#!/usr/bin/env python3
"""Validate database quality after import."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import db_session, init_db

POLLUTED_MARKERS = ("Header:", "Specific long description about this code:")


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

        emb = conn.execute("SELECT COUNT(*) AS c FROM term_embeddings").fetchone()["c"]
        terms = conn.execute("SELECT COUNT(*) AS c FROM terms").fetchone()["c"]
        if terms > 1000 and emb == 0:
            errors.append("semantic index empty — run build_semantic_index.py or use keyword mode")

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("Validation passed.")


if __name__ == "__main__":
    main()
