#!/usr/bin/env python3
"""Import NLM curated conditions and procedures."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import (
    add_synonym,
    db_session,
    init_db,
    log_import,
    upsert_en_translation,
)
from scripts.common import RAW_DIR

CONDITIONS_CSV = RAW_DIR / "nlm_conditions.csv"
CONDITIONS_JSON = RAW_DIR / "nlm_conditions.json"
PROCEDURES_CSV = RAW_DIR / "nlm_procedures.csv"
PROCEDURES_JSON = RAW_DIR / "nlm_procedures.json"

PROCEDURE_SPECIALTY_HINTS: dict[str, str] = {
    "appendectomy": "gi",
    "cholecystectomy": "gi",
    "gastrectomy": "gi",
    "colectomy": "gi",
    "hernia": "gi",
    "mastectomy": "general",
    "thyroidectomy": "general",
    "prostatectomy": "urology",
    "nephrectomy": "urology",
    "craniotomy": "neurosurgery",
    "arthroplasty": "orthopaedic",
    "cataract": "ophthalmology",
    "bypass": "cardiothoracic",
    "valve": "cardiothoracic",
}


def split_synonyms(value: str | None) -> list[str]:
    if not value:
        return []
    return [s.strip() for s in value.replace("|", ";").split(";") if s.strip()]


def import_conditions(conn) -> int:
    count = 0
    if CONDITIONS_CSV.exists():
        with CONDITIONS_CSV.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    elif CONDITIONS_JSON.exists():
        raw = json.loads(CONDITIONS_JSON.read_text(encoding="utf-8"))
        rows = []
        for item in raw:
            if isinstance(item, list):
                rows.append({"primary_name": item[0] if item else ""})
            elif isinstance(item, dict):
                rows.append(item)
    else:
        print("No NLM conditions file found; run download_sources.py first.")
        return 0

    for row in rows:
        primary = row.get("primary_name") or row.get("consumer_name") or ""
        if not primary:
            continue
        consumer = row.get("consumer_name") or None
        key_id = row.get("key_id") or row.get("KEY_ID")
        cur = conn.execute(
            """
            INSERT INTO terms (kind, code, code_system, primary_name, consumer_name, layer, active)
            VALUES ('diagnosis', ?, 'NLM', ?, ?, 'curated', 1)
            """,
            (key_id, primary, consumer),
        )
        term_id = cur.lastrowid
        upsert_en_translation(conn, term_id, primary, consumer)
        for syn in split_synonyms(row.get("synonyms")) + split_synonyms(row.get("word_synonyms")):
            add_synonym(conn, term_id, syn, "en", "nlm")
        count += 1
    return count


def infer_specialty(name: str) -> str | None:
    lower = name.lower()
    for hint, specialty in PROCEDURE_SPECIALTY_HINTS.items():
        if hint in lower:
            return specialty
    return None


def import_procedures(conn) -> int:
    count = 0
    if PROCEDURES_CSV.exists():
        with PROCEDURES_CSV.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    elif PROCEDURES_JSON.exists():
        raw = json.loads(PROCEDURES_JSON.read_text(encoding="utf-8"))
        rows = []
        for item in raw:
            if isinstance(item, list):
                rows.append({"primary_name": item[0] if item else ""})
            elif isinstance(item, dict):
                rows.append(item)
    else:
        print("No NLM procedures file found; run download_sources.py first.")
        return 0

    for row in rows:
        primary = row.get("primary_name") or ""
        if not primary:
            continue
        consumer = row.get("consumer_name") or None
        key_id = row.get("key_id") or row.get("KEY_ID")
        cur = conn.execute(
            """
            INSERT INTO terms (kind, code, code_system, primary_name, consumer_name, layer, is_surgical, specialty, active)
            VALUES ('procedure', ?, 'NLM', ?, ?, 'curated', 1, ?, 1)
            """,
            (key_id, primary, consumer, infer_specialty(primary)),
        )
        term_id = cur.lastrowid
        upsert_en_translation(conn, term_id, primary, consumer)
        for syn in split_synonyms(row.get("synonyms")) + split_synonyms(row.get("word_synonyms")):
            add_synonym(conn, term_id, syn, "en", "nlm")
        count += 1
    return count


def main() -> None:
    init_db()
    with db_session() as conn:
        conn.execute("DELETE FROM terms WHERE code_system = 'NLM'")
        dx = import_conditions(conn)
        px = import_procedures(conn)
        log_import(conn, "nlm_conditions", "curated", dx)
        log_import(conn, "nlm_procedures", "curated", px)
    print(f"Imported {dx} conditions and {px} procedures from NLM curated tables.")


if __name__ == "__main__":
    main()
