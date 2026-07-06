#!/usr/bin/env python3
"""Import CDC ICD-10-CM diagnosis codes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import add_synonym, db_session, init_db, log_import, upsert_en_translation
from scripts.common import RAW_DIR, print_reindex_warning

ORDER_FILE = RAW_DIR / "icd10cm-order.txt"
CSV_FILE = RAW_DIR / "icd10cm_data.csv"

CSV_DESC_SPLIT = "| Specific long description about this code:"
POLLUTED_MARKERS = ("Header:", "Specific long description about this code:")


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
    }


def clean_csv_description(desc: str) -> str:
    if CSV_DESC_SPLIT in desc:
        return desc.split(CSV_DESC_SPLIT)[-1].strip()
    if desc.startswith("Header:"):
        # Header: K358 - Title | Specific...
        m = re.search(r"Header:\s*\S+\s*-\s*(.+?)(?:\s*\|\s*Specific|$)", desc)
        if m:
            return m.group(1).strip()
    for marker in POLLUTED_MARKERS:
        if marker in desc:
            return desc.split(marker)[-1].strip().lstrip(": ").strip()
    return desc.strip()


def is_polluted_name(name: str) -> bool:
    return any(marker in name for marker in POLLUTED_MARKERS)


def import_from_order(conn) -> int:
    count = 0
    with ORDER_FILE.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse_icd10cm_line(line.rstrip("\n"))
            if not parsed or not parsed["billable"]:
                continue
            code = parsed["code"]
            desc = parsed["short_desc"]
            if not desc or is_polluted_name(desc):
                continue
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
    return count


def import_from_csv(conn) -> int:
    import pandas as pd

    df = pd.read_csv(CSV_FILE, dtype=str)
    code_col = "code" if "code" in df.columns else df.columns[0]
    desc_col = "description" if "description" in df.columns else df.columns[1]
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        code = str(row.get(code_col, "")).strip()
        desc = clean_csv_description(str(row.get(desc_col, "") or "").strip())
        if not code or not desc or desc.lower() == "nan":
            continue
        if is_polluted_name(desc):
            skipped += 1
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
    if skipped:
        print(f"  skipped {skipped} rows with unparsable polluted descriptions")
    return count


def main() -> None:
    if ORDER_FILE.exists():
        source = "icd10cm-order.txt"
    elif CSV_FILE.exists():
        source = "icd10cm_data.csv (cleaned)"
    else:
        raise FileNotFoundError("Missing ICD-10-CM source; run download_sources.py")

    init_db()
    with db_session() as conn:
        conn.execute("DELETE FROM terms WHERE code_system = 'ICD-10-CM'")
        if ORDER_FILE.exists():
            count = import_from_order(conn)
        else:
            count = import_from_csv(conn)
        log_import(conn, "icd10cm", source, count)
    print(f"Imported {count} ICD-10-CM diagnosis codes from {source}.")
    print_reindex_warning()


if __name__ == "__main__":
    main()
