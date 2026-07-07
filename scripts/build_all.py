#!/usr/bin/env python3
"""Run full ETL pipeline: download → import → index."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

STEPS = [
    "download_sources.py",
    "import_curated.py",
    "backfill_nlm_specialties.py",
    "import_icd10cm.py",
    "import_icd10pcs.py",
    "import_icd10am_ro.py",
    "translate_curated_ro.py",
    "enrich_metadata.py",
    "seed_video_sources.py",
    "build_search_index.py",
    "build_semantic_index.py",
    "validate_db.py",
]


def run_step(script: str) -> None:
    path = SCRIPTS / script
    print(f"\n=== {script} ===")
    subprocess.run([sys.executable, str(path)], check=True)


def main() -> None:
    for step in STEPS:
        try:
            run_step(step)
        except subprocess.CalledProcessError as exc:
            print(f"Step failed: {step} (exit {exc.returncode})")
            if step == "download_sources.py":
                raise
            print("Continuing with remaining steps where possible...")
    print("\nBuild pipeline complete.")


if __name__ == "__main__":
    main()
