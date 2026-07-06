#!/usr/bin/env python3
"""Batch-translate curated NLM terms to Romanian (offline ETL, stored in DB)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import add_synonym, db_session, init_db, log_import, upsert_ro_translation

OVERRIDES = ROOT / "data" / "curated_ro_overrides.csv"

# Surgical glossary for reliable offline translation without external APIs.
GLOSSARY = {
    "appendectomy": "apendicectomie",
    "cholecystectomy": "colecistectomie",
    "gastrectomy": "gastrectomie",
    "colectomy": "colectomie",
    "mastectomy": "mastectomie",
    "thyroidectomy": "tiroidectomie",
    "prostatectomy": "prostatectomie",
    "nephrectomy": "nefrectomie",
    "hysterectomy": "histerectomie",
    "cesarean section": "cesariană",
    "hernia": "hernie",
    "laparoscopic": "laparoscopic",
    "open": "deschis",
    "repair": "reparare",
    "bypass": "bypass",
    "resection": "rezecție",
    "amputation": "amputație",
    "biopsy": "biopsie",
    "stent": "stent",
    "catheter": "cateter",
    "fracture": "fractură",
    "cancer": "cancer",
    "tumor": "tumoră",
    "infection": "infecție",
    "diabetes": "diabet",
    "hypertension": "hipertensiune",
    "pneumonia": "pneumonie",
    "appendicitis": "apendicită",
    "cholecystitis": "colecistită",
    "surgery": "chirurgie",
    "surgical": "chirurgical",
}


def translate_text(text: str) -> str:
    lower = text.lower()
    if lower in GLOSSARY:
        return GLOSSARY[lower]
    result = text
    for en, ro in sorted(GLOSSARY.items(), key=lambda x: -len(x[0])):
        if en in lower:
            result = result.replace(en, ro).replace(en.capitalize(), ro.capitalize())
    return result


def load_overrides() -> dict[str, str]:
    if not OVERRIDES.exists():
        return {}
    mapping = {}
    with OVERRIDES.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            en = (row.get("en") or "").strip()
            ro = (row.get("ro") or "").strip()
            if en and ro:
                mapping[en.lower()] = ro
    return mapping


def main() -> None:
    init_db()
    overrides = load_overrides()
    count = 0

    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.primary_name, t.consumer_name
            FROM terms t
            LEFT JOIN term_translations tr ON tr.term_id = t.id AND tr.locale = 'ro'
            WHERE t.layer = 'curated' AND tr.term_id IS NULL
            """
        ).fetchall()

        for row in rows:
            primary = row["primary_name"]
            consumer = row["consumer_name"]
            ro_primary = overrides.get(primary.lower()) or translate_text(primary)
            ro_consumer = None
            if consumer:
                ro_consumer = overrides.get(consumer.lower()) or translate_text(consumer)

            upsert_ro_translation(conn, row["id"], ro_primary, ro_consumer)
            add_synonym(conn, row["id"], ro_primary, "ro", "translated")
            if ro_consumer and ro_consumer != ro_primary:
                add_synonym(conn, row["id"], ro_consumer, "ro", "translated")
            count += 1

        log_import(conn, "curated_ro_translations", "glossary+overrides", count)

    print(f"Added Romanian translations for {count} curated terms.")


if __name__ == "__main__":
    main()
