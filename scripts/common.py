import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"

REINDEX_WARNING = """
WARNING: This importer deletes and re-inserts terms (cascading translations/embeddings).
Re-run before serving:
  python scripts/translate_curated_ro.py
  python scripts/enrich_metadata.py
  python scripts/build_search_index.py
  python scripts/build_semantic_index.py
Or run: python scripts/build_all.py
"""


def print_reindex_warning() -> None:
    print(REINDEX_WARNING.strip())


def save_manifest(entries: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if MANIFEST_PATH.exists():
        existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    existing.update(entries)
    MANIFEST_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
