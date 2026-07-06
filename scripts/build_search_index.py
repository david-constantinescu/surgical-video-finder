#!/usr/bin/env python3
"""Build FTS5 keyword index over EN and RO term text."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import db_session, init_db, log_import

FTS_SCHEMA = """
DROP TABLE IF EXISTS terms_fts;
CREATE VIRTUAL TABLE terms_fts USING fts5(
  term_id UNINDEXED,
  primary_name_en,
  consumer_name_en,
  primary_name_ro,
  consumer_name_ro,
  code,
  aliases_en,
  aliases_ro,
  tokenize='unicode61 remove_diacritics 0'
);
"""


def main() -> None:
    init_db()
    with db_session() as conn:
        conn.executescript(FTS_SCHEMA)

        rows = conn.execute(
            """
            SELECT
              t.id,
              t.code,
              t.primary_name,
              t.consumer_name,
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
        ).fetchall()

        conn.executemany(
            """
            INSERT INTO terms_fts (
              term_id, primary_name_en, consumer_name_en,
              primary_name_ro, consumer_name_ro, code, aliases_en, aliases_ro
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["id"],
                    r["en_name"] or "",
                    r["en_consumer"] or "",
                    r["ro_name"] or "",
                    r["ro_consumer"] or "",
                    r["code"] or "",
                    r["aliases_en"] or "",
                    r["aliases_ro"] or "",
                )
                for r in rows
            ],
        )
        log_import(conn, "terms_fts", "fts5", len(rows))
    print(f"Built FTS5 index for {len(rows)} terms.")


if __name__ == "__main__":
    main()
