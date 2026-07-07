#!/usr/bin/env python3
"""Backfill NLM procedure specialty tags from hint dictionary (no re-import)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import db_session, init_db
from scripts.import_curated import infer_specialty_for_term


def backfill_nlm_specialties(conn) -> int:
    rows = conn.execute(
        """
        SELECT id, primary_name, consumer_name, specialty
        FROM terms
        WHERE code_system = 'NLM' AND kind = 'procedure'
        """
    ).fetchall()
    updated = 0
    for row in rows:
        inferred = infer_specialty_for_term(row["primary_name"], row["consumer_name"])
        if not inferred or inferred == row["specialty"]:
            continue
        conn.execute("UPDATE terms SET specialty = ? WHERE id = ?", (inferred, row["id"]))
        updated += 1
    return updated


def main() -> None:
    init_db()
    with db_session() as conn:
        updated = backfill_nlm_specialties(conn)
        tagged = conn.execute(
            """
            SELECT COUNT(*) AS c FROM terms
            WHERE code_system = 'NLM' AND kind = 'procedure' AND specialty IS NOT NULL
            """
        ).fetchone()["c"]
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM terms WHERE code_system = 'NLM' AND kind = 'procedure'"
        ).fetchone()["c"]
    print(f"Updated {updated} NLM procedures; {tagged}/{total} now have specialty tags.")


if __name__ == "__main__":
    main()
