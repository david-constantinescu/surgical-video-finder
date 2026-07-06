#!/usr/bin/env python3
"""Import CMS ICD-10-PCS procedure codes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import add_synonym, db_session, init_db, log_import, upsert_en_translation
from scripts.common import RAW_DIR, print_reindex_warning

CODES_FILE = RAW_DIR / "icd10pcs-codes.txt"
LEGACY_FILE = RAW_DIR / "icd10pcs-order.txt"

PCS_CODE_RE = re.compile(r"^[0-9A-HJ-NP-Z]{7}$")


def parse_pcs_line(line: str) -> dict | None:
    line = line.strip()
    if len(line) < 9:
        return None
    code = line[:7].strip().upper()
    desc = line[7:].strip()
    if not PCS_CODE_RE.match(code) or not desc:
        return None
    return {"code": code, "desc": desc}


def main() -> None:
    source = CODES_FILE if CODES_FILE.exists() else LEGACY_FILE
    if not source.exists():
        raise FileNotFoundError("Missing ICD-10-PCS source; run download_sources.py")

    init_db()
    count = 0
    with db_session() as conn:
        conn.execute("DELETE FROM terms WHERE code_system = 'ICD-10-PCS'")
        with source.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                parsed = parse_pcs_line(line)
                if not parsed:
                    continue
                cur = conn.execute(
                    """
                    INSERT INTO terms (
                      kind, code, code_system, primary_name, layer, active
                    ) VALUES ('procedure', ?, 'ICD-10-PCS', ?, 'comprehensive', 1)
                    """,
                    (parsed["code"], parsed["desc"]),
                )
                term_id = cur.lastrowid
                upsert_en_translation(conn, term_id, parsed["desc"])
                add_synonym(conn, term_id, parsed["code"], "en", "icd_code")
                count += 1
        log_import(conn, "icd10pcs", "FY2025", count)
    print(f"Imported {count} ICD-10-PCS procedure codes.")
    print_reindex_warning()


if __name__ == "__main__":
    main()
