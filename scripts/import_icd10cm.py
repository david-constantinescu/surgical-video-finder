#!/usr/bin/env python3
"""Import CDC ICD-10-CM diagnosis codes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import add_synonym, db_session, init_db, log_import, upsert_en_translation
from scripts.common import RAW_DIR

ORDER_FILE = RAW_DIR / "icd10cm-order.txt"
CSV_FILE = RAW_DIR / "icd10cm_data.csv"


def parse_icd10cm_line(line: str) -> dict | None:
    if len(line) < 77:
        return None
    code = line[6:14].strip()
    billable = line[14:16].strip()
    short_desc = line[16:77].strip()
    if not code:
        return None
    return {
        "code": code,
        "billable": billable == "1",
        "short_desc": short_desc,
        "long_desc": short_desc,
    }


def import_from_csv(conn) -> int:
    import pandas as pd

    df = pd.read_csv(CSV_FILE, dtype=str)
    code_col = "code" if "code" in df.columns else df.columns[0]
    desc_col = "description" if "description" in df.columns else df.columns[1]
    count = 0
    for _, row in df.iterrows():
        code = str(row.get(code_col, "")).strip()
        desc = str(row.get(desc_col, "")).strip()
        if not code or not desc or desc.lower() == "nan":
            continue
        cur = conn.execute(
            """
            INSERT INTO terms (kind, code, code_system, primary_name, layer, active)
            VALUES ('diagnosis', ?, 'ICD-10-CM', ?, 'comprehensive', 1)
            """,
            (code, desc),
        )
        term_id = cur.lastrowid
        upsert_en_translation(conn, term_id, desc)
        add_synonym(conn, term_id, code, "en", "icd_code")
        count += 1
    return count


def main() -> None:
    init_db()
    count = 0
    with db_session() as conn:
        if CSV_FILE.exists():
            count = import_from_csv(conn)
        elif ORDER_FILE.exists():
            with ORDER_FILE.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    parsed = parse_icd10cm_line(line.rstrip("\n"))
                    if not parsed or not parsed["billable"]:
                        continue
                    code = parsed["code"]
                    desc = parsed["short_desc"]
                    cur = conn.execute(
                        """
                        INSERT INTO terms (
                          kind, code, code_system, primary_name, layer, active
                        ) VALUES ('diagnosis', ?, 'ICD-10-CM', ?, 'comprehensive', 1)
                        """,
                        (code, desc),
                    )
                    term_id = cur.lastrowid
                    upsert_en_translation(conn, term_id, desc)
                    add_synonym(conn, term_id, code, "en", "icd_code")
                    count += 1
        else:
            raise FileNotFoundError(f"Missing ICD-10-CM source; run download_sources.py")
        log_import(conn, "icd10cm", "FY2026", count)
    print(f"Imported {count} ICD-10-CM diagnosis codes.")


if __name__ == "__main__":
    main()
