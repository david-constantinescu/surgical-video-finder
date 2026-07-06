#!/usr/bin/env python3
"""Download raw terminology and mapping source files."""

from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import requests

from scripts.common import RAW_DIR, save_manifest

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "surgical-video-finder/1.0"})

SOURCES = {
    "icd10cm_order": {
        "url": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026/icd10cm-Code%20Descriptions-2026.zip",
        "filename": "icd10cm-code-descriptions-2026.zip",
        "version": "FY2026",
        "inner_ext": ".txt",
        "extract_as": "icd10cm-order.txt",
    },
    "icd10cm_csv_fallback": {
        "url": "https://raw.githubusercontent.com/stabgan/ICD-10-CM-code-April-2025-CSV-FILE-ENHANCED/main/icd10cm_data.csv",
        "filename": "icd10cm_data.csv",
        "version": "April-2025-CSV",
        "optional": True,
    },
    "icd10pcs_order": {
        "url": "https://www.cms.gov/files/zip/2025-icd-10-pcs-codes-file.zip",
        "filename": "icd10pcs-codes-2025.zip",
        "version": "FY2025",
        "inner_txt": "icd10pcs_codes_2025.txt",
        "extract_as": "icd10pcs-codes.txt",
    },
    "nlm_conditions": {
        "url": "https://clinicaltables.nlm.nih.gov/ctss-downloads/conditions.csv",
        "filename": "nlm_conditions.csv",
        "version": "2025-10-01",
        "fallback_api": "https://clinicaltables.nlm.nih.gov/api/conditions/v3/search",
    },
    "nlm_procedures": {
        "url": "https://clinicaltables.nlm.nih.gov/ctss-downloads/procedures.csv",
        "filename": "nlm_procedures.csv",
        "version": "2025-10-01",
        "fallback_api": "https://clinicaltables.nlm.nih.gov/api/procedures/v3/search",
    },
    "icd_mappings_procedures": {
        "url": "https://raw.githubusercontent.com/mpopuri2/icd-mappings/main/data/procedure_category_mapping_full.csv",
        "filename": "procedure_category_mapping_full.csv",
        "version": "2026",
        "optional": True,
    },
    "icd_mappings_diagnoses": {
        "url": "https://raw.githubusercontent.com/mpopuri2/icd-mappings/main/data/hcc_diagnosis_mapping_full.csv",
        "filename": "hcc_diagnosis_mapping_full.csv",
        "version": "2026",
        "optional": True,
    },
    "ro_icd10am_diagnoses": {
        "url": "https://www.icd10.ro/export.php?format=xlsx",
        "filename": "icd10am_ro_diagnoses.xlsx",
        "version": "icd10.ro",
        "optional": True,
    },
    "ro_achi_procedures_pdf": {
        "url": "http://www.sant.ro/informatii-utile/statistica-si-informatica/clasificare-ro.vi.drg/1/1/ListaTabelara_proceduri_ICD_10_AM.pdf/at_download/file",
        "filename": "ro_achi_procedures.pdf",
        "version": "ICD-10-AM-RO",
        "optional": True,
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(key: str, meta: dict) -> Path | None:
    dest = RAW_DIR / meta["filename"]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip (exists): {dest.name}")
        return dest

    print(f"  downloading: {meta['url']}")
    try:
        resp = SESSION.get(meta["url"], timeout=120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        if meta.get("optional"):
            print(f"  optional source failed ({key}): {exc}")
            return None
        raise

    content = resp.content
    if key == "icd10pcs_order":
        with zipfile.ZipFile(BytesIO(content)) as zf:
            inner_name = meta.get("inner_txt")
            names = [inner_name] if inner_name and inner_name in zf.namelist() else []
            if not names:
                names = [n for n in zf.namelist() if n.lower().endswith(".txt") and "pcs" in n.lower()]
            if not names:
                names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not names:
                raise RuntimeError("No .txt file in ICD-10-PCS zip")
            dest_txt = RAW_DIR / meta.get("extract_as", "icd10pcs-codes.txt")
            dest_txt.write_bytes(zf.read(names[0]))
            dest = dest_txt
    elif key == "icd10cm_order":
        with zipfile.ZipFile(BytesIO(content)) as zf:
            ext = meta.get("inner_ext", ".txt")
            names = [n for n in zf.namelist() if n.lower().endswith(ext)]
            if not names:
                names = [n for n in zf.namelist() if "order" in n.lower() or "tabular" in n.lower()]
            if not names:
                raise RuntimeError("No suitable file in ICD-10-CM zip")
            dest_txt = RAW_DIR / meta.get("extract_as", "icd10cm-order.txt")
            dest_txt.write_bytes(zf.read(names[0]))
            dest = dest_txt
    else:
        dest.write_bytes(content)

    print(f"  saved: {dest} ({dest.stat().st_size} bytes)")
    return dest


def fetch_nlm_via_api(api_url: str, dest: Path, display_field: int = 0) -> None:
    """Paginate NLM clinical tables API when CSV download is unavailable."""
    print(f"  fetching via API: {api_url}")
    rows: list[list] = []
    for letter in "abcdefghijklmnopqrstuvwxyz0123456789":
        resp = SESSION.get(
            api_url,
            params={"terms": letter, "maxList": 500, "ef": "primary_name,consumer_name,synonyms,word_synonyms"},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        if len(payload) < 4 or not payload[3]:
            continue
        for item in payload[3]:
            if item not in rows:
                rows.append(item)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  API fallback saved {len(rows)} rows to {dest}")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {}

    for key, meta in SOURCES.items():
        try:
            path = download_file(key, meta)
        except requests.RequestException as exc:
            print(f"  failed {key}: {exc}")
            if key in ("nlm_conditions", "nlm_procedures") and "fallback_api" in meta:
                dest = RAW_DIR / meta["filename"].replace(".csv", ".json")
                fetch_nlm_via_api(meta["fallback_api"], dest)
                path = dest
            elif not meta.get("optional"):
                raise
            else:
                continue

        if path and path.exists():
            manifest[key] = {
                "path": str(path.relative_to(RAW_DIR.parent.parent)),
                "sha256": sha256_file(path),
                "version": meta.get("version"),
                "size": path.stat().st_size,
            }

    save_manifest(manifest)
    print(f"\nManifest written to {RAW_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
