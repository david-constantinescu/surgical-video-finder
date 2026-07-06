# Getting started

## Prerequisites

- Python 3.10+
- ~2 GB free disk (raw downloads + SQLite + embedding model cache)
- Internet for first-time `build_all.py`

## Install

```bash
cd surgical-video-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional API keys
```

## Build the database

```bash
python scripts/build_all.py
```

| Step | Time (approx.) | Output |
|------|----------------|--------|
| Download sources | 1–3 min | `data/raw/` |
| Import terminology | 2–5 min | `data/surgical.db` |
| FTS index | <1 min | Full-text search |
| Semantic index | 10–20 min | Embeddings + `data/embeddings/` |

**Skip semantic for a faster smoke test** (keyword search only):

```bash
python scripts/download_sources.py
python scripts/import_curated.py
python scripts/import_icd10cm.py
python scripts/import_icd10pcs.py
python scripts/import_icd10am_ro.py
python scripts/translate_curated_ro.py
python scripts/enrich_metadata.py
python scripts/seed_video_sources.py
python scripts/build_search_index.py
```

## Run the app

```bash
python -m app.server
# or: flask --app app.server run --port 5001
```

Visit http://localhost:5001

## Typical workflow

1. Choose **EN** or **RO** in the header.
2. Search for diagnoses or procedures (e.g. `appendectomy`, `apendicectomie`).
3. Click **Add** on results to build your selection.
4. Click **Find videos** — outbound links to 46 platforms, plus **inline YouTube thumbnails** and PubMed articles (no API keys required).

### Inline videos (no API keys required)

**Find videos** shows YouTube thumbnails and PubMed articles out of the box — no API keys needed. Click **Play** to embed YouTube in-page.

Optional upgrades:
- `YOUTUBE_API_KEY` — official YouTube Data API (more reliable at scale)
- `VIMEO_TOKEN` — inline Vimeo results
- `NOKEY_SEARCH_INSTANCES` — comma-separated Piped/Invidious bases if defaults are down

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `No terms to embed` | Run import scripts before `build_semantic_index.py` |
| Empty search results | Run `build_search_index.py` after imports |
| Reimported NLM/ICD rows but RO search broken | Importers cascade-delete translations/embeddings — re-run `translate_curated_ro.py`, `enrich_metadata.py`, `build_search_index.py`, `build_semantic_index.py` (or `build_all.py`) |
| Port 5000 in use (macOS AirPlay) | Default is **5001**; set `FLASK_PORT` in `.env` |
| No YouTube thumbnails, only links | Public Piped/Invidious instances may be down — set `NOKEY_SEARCH_INSTANCES` or optional `YOUTUBE_API_KEY`; check `/api/health` for `"youtube": true` |
| Romanian labels show `[EN]` | Optional `icd10.ro` Excel failed to download; add overrides in `data/curated_ro_overrides.csv` |

## Health check

```bash
curl http://localhost:5001/api/health
```

Expected: `"terms": 161000+`, `"video_sources": 46`
