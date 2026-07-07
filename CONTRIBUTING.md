# Contributing to Surgical Video Finder

Thanks for helping improve the project. This app is a local-first Flask + SQLite tool for bilingual surgical term search and video discovery.

## Development setup

```bash
git clone https://github.com/david-constantinescu/surgical-video-finder.git
cd surgical-video-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Build the database (first run only; may take 30–60 minutes):

```bash
python scripts/build_all.py
```

Run the app:

```bash
python -m app.server
```

Open http://localhost:5001

## Quality checks

Before opening a pull request:

```bash
pytest -q
ruff check .
python scripts/validate_db.py   # requires a built database
```

CI runs the same test and lint steps on every push.

## Project layout

| Path | Purpose |
|------|---------|
| `app/` | Flask server, search, inline video providers, UI static assets |
| `scripts/` | ETL pipeline (download → import → index → validate) |
| `tests/` | pytest unit tests |
| `docs/` | Architecture, data sources, i18n, video catalog |

## Making changes

### Search or ranking

- Hybrid search lives in `app/search.py` (FTS5 keyword + semantic embeddings + RRF merge).
- Tune thresholds via `.env` (`SEMANTIC_MIN_SIMILARITY`, `RRF_K` in config).

### Inline videos

- YouTube/Vimeo no-key search: `app/nokey_search.py`, `app/nokey_vimeo.py`
- Official API fallbacks: `app/youtube_search.py`, `app/vimeo_search.py`
- PubMed articles: `app/pubmed_search.py`
- Shared cache: `app/video_cache.py`

### Data imports

Destructive importers (`import_curated.py`, `import_icd10cm.py`, `import_icd10pcs.py`) cascade-delete translations and embeddings. After any of these, re-run:

```bash
python scripts/translate_curated_ro.py
python scripts/enrich_metadata.py
python scripts/build_search_index.py
python scripts/build_semantic_index.py
```

Or run `python scripts/build_all.py`.

NLM specialty tags can be refreshed without a full re-import:

```bash
python scripts/backfill_nlm_specialties.py
```

### i18n

UI strings are in `app/i18n/en.json` and `app/i18n/ro.json`. Keep keys in sync across both files.

## Pull request guidelines

- Keep diffs focused; one logical change per PR when possible.
- Add or update tests for behavior changes.
- Update docs when user-facing behavior or setup steps change.
- Do not commit `data/surgical.db`, embeddings, or API keys.

## License

MIT — see [LICENSE](LICENSE). Upstream medical coding data remains under its respective licenses.
