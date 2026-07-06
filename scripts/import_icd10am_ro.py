#!/usr/bin/env python3
"""Import Romanian ICD-10-AM diagnoses and ACHI procedures."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from app.db import (
    add_synonym,
    db_session,
    find_term_by_code,
    init_db,
    log_import,
    upsert_ro_translation,
)
from scripts.common import RAW_DIR

RO_XLSX = RAW_DIR / "icd10am_ro_diagnoses.xlsx"
RO_PDF = RAW_DIR / "ro_achi_procedures.pdf"

ICD_CODE_RE = re.compile(r"^[A-TV-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$")
ACHI_CODE_RE = re.compile(r"^\d{1,5}(?:-\d{2})?$")


def normalize_icd_code(code: str) -> str:
    return code.strip().upper().replace(" ", "")


def import_ro_diagnoses_xlsx(conn) -> int:
    if not RO_XLSX.exists():
        print("Romanian diagnosis xlsx not found; skipping xlsx import.")
        return 0

    df = pd.read_excel(RO_XLSX, dtype=str)
    cols = {c.lower().strip(): c for c in df.columns}
    code_col = cols.get("cod") or cols.get("code") or list(df.columns)[0]
    name_col = cols.get("denumire") or cols.get("name") or list(df.columns)[1]

    count = 0
    for _, row in df.iterrows():
        code = normalize_icd_code(str(row.get(code_col, "") or ""))
        name = str(row.get(name_col, "") or "").strip()
        if not code or not name or name.lower() == "nan":
            continue
        if not ICD_CODE_RE.match(code.replace(".", "").replace("-", "")[:3] + code[3:]):
            # still try if looks like ICD
            if len(code) < 3:
                continue

        existing_id = find_term_by_code(conn, code, "ICD-10-CM")
        if existing_id:
            upsert_ro_translation(conn, existing_id, name)
            add_synonym(conn, existing_id, name, "ro", "icd10am")
            count += 1
        else:
            cur = conn.execute(
                """
                INSERT INTO terms (kind, code, code_system, primary_name, layer, active)
                VALUES ('diagnosis', ?, 'ICD-10-AM-RO', ?, 'comprehensive', 1)
                """,
                (code, name),
            )
            term_id = cur.lastrowid
            upsert_ro_translation(conn, term_id, name)
            add_synonym(conn, term_id, name, "ro", "icd10am")
            count += 1
    return count


def import_ro_procedures_pdf(conn) -> int:
    if not RO_PDF.exists():
        print("Romanian ACHI PDF not found; skipping procedure import.")
        return 0

    try:
        import pdfplumber
    except ImportError:
        print("pdfplumber not installed; skipping ACHI PDF import.")
        return 0

    count = 0
    with pdfplumber.open(RO_PDF) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                code, name = parts[0], parts[1].strip()
                if not ACHI_CODE_RE.match(code):
                    continue
                if len(name) < 4:
                    continue

                cur = conn.execute(
                    """
                    INSERT INTO terms (kind, code, code_system, primary_name, layer, is_surgical, active)
                    VALUES ('procedure', ?, 'ACHI-RO', ?, 'comprehensive', 1, 1)
                    """,
                    (code, name),
                )
                term_id = cur.lastrowid
                upsert_ro_translation(conn, term_id, name)
                add_synonym(conn, term_id, name, "ro", "achi")
                count += 1
    return count


def seed_common_ro_translations(conn) -> int:
    """Fallback RO labels for common surgical terms when official files are missing."""
    common = {
        "appendectomy": "apendicectomie",
        "cholecystectomy": "colecistectomie",
        "hernia repair": "reparare hernie",
        "gastrectomy": "gastrectomie",
        "colectomy": "colectomie",
        "thyroidectomy": "tiroidectomie",
        "mastectomy": "mastectomie",
        "prostatectomy": "prostatectomie",
        "nephrectomy": "nefrectomie",
        "laparoscopic": "laparoscopic",
        "open surgery": "chirurgie deschisă",
    }
    count = 0
    for en, ro in common.items():
        rows = conn.execute(
            """
            SELECT id FROM terms
            WHERE lower(primary_name) LIKE ?
            LIMIT 5
            """,
            (f"%{en}%",),
        ).fetchall()
        for row in rows:
            upsert_ro_translation(conn, row["id"], ro)
            add_synonym(conn, row["id"], ro, "ro", "seed")
            count += 1
    return count


def main() -> None:
    init_db()
    with db_session() as conn:
        dx = import_ro_diagnoses_xlsx(conn)
        px = import_ro_procedures_pdf(conn)
        seed = seed_common_ro_translations(conn)
        log_import(conn, "icd10am_ro_diagnoses", "icd10.ro", dx)
        log_import(conn, "achi_ro_procedures", "SANT PDF", px)
        log_import(conn, "ro_seed_translations", "fallback", seed)
    print(f"Romanian import: {dx} diagnosis translations, {px} procedures, {seed} seed links.")


if __name__ == "__main__":
    main()
