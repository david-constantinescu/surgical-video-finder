#!/usr/bin/env python3
"""Enrich procedure terms with surgical flags and specialty from icd-mappings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from app.db import db_session, init_db, log_import
from scripts.common import RAW_DIR

MAPPING_FILE = RAW_DIR / "procedure_category_mapping_full.csv"


def main() -> None:
    if not MAPPING_FILE.exists():
        print(f"Skipping enrichment: {MAPPING_FILE} not found (optional source).")
        return

    df = pd.read_csv(MAPPING_FILE, dtype=str, low_memory=False)
    if "ICD_VERSION" in df.columns:
        df = df[df["ICD_VERSION"].astype(str).str.strip() == "10"]
    code_col = "ICD_CODE" if "ICD_CODE" in df.columns else df.columns[0]

    init_db()
    updated = 0
    with db_session() as conn:
        for _, row in df.iterrows():
            code = str(row.get(code_col, "")).strip()
            if not code:
                continue
            specialty = row.get("CLINICAL_SPECIALTY") or row.get("PROCEDURE_CATEGORY")
            is_surgical = 1 if str(row.get("IS_SURGICAL", "0")).strip() in ("1", "True", "true") else 0
            complexity = row.get("COMPLEXITY_TIER")
            cur = conn.execute(
                """
                UPDATE terms SET specialty = ?, is_surgical = ?, complexity = ?
                WHERE code = ? AND code_system = 'ICD-10-PCS'
                """,
                (specialty, is_surgical, complexity, code),
            )
            updated += cur.rowcount
        log_import(conn, "icd_mappings_enrichment", "2026", updated)
    print(f"Enriched {updated} ICD-10-PCS terms with mapping metadata.")


if __name__ == "__main__":
    main()
