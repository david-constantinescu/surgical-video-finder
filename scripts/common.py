import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"


def save_manifest(entries: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if MANIFEST_PATH.exists():
        existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    existing.update(entries)
    MANIFEST_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
