# Architecture

Surgical Video Finder is a local-first Flask application backed by SQLite. It helps surgeons build a multi-term case list (diagnoses and procedures), search terminology in English or Romanian, and open video resources on external platforms.

## Components

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (HTML / CSS / JS)                                  │
│  - Language toggle (EN / RO)                                │
│  - Autocomplete search + multi-select chips                 │
│  - Video link panel                                         │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST JSON
┌───────────────────────────▼─────────────────────────────────┐
│  Flask (`app/server.py`)                                    │
│  - `/api/terms/search`  hybrid / keyword / semantic         │
│  - `/api/videos/links`  URL template builder                  │
│  - `/api/i18n/{lang}`   UI strings                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  `app/search.py`    `app/video_links.py`   `app/db.py`
  hybrid ranking     46 video sources       SQLite schema
        │                   │
        ▼                   ▼
  FTS5 + numpy         `video_sources` table
  embeddings           (hyperlink templates)
```

## Data flow: terminology

1. **Download** — `scripts/download_sources.py` fetches CDC ICD-10-CM, CMS ICD-10-PCS, NLM curated tables (API fallback), icd-mappings enrichment CSVs, Romanian ACHI PDF.
2. **Import** — separate scripts load rows into `terms`, `term_translations`, `synonyms`.
3. **Index** — `build_search_index.py` rebuilds FTS5; `build_semantic_index.py` encodes multilingual embeddings.
4. **Serve** — `search.py` merges keyword and vector scores at query time.

## Data flow: videos (Phase 1)

Phase 1 does **not** scrape or embed videos. `video_links.py` builds outbound URLs from:

- Selected term display names (locale-aware)
- Per-source URL templates in `video_sources`
- Query suffixes (`surgery`, `chirurgie`, `operative video`, etc.)

Phase 2 (planned) adds YouTube Data API caching into `video_results`.

## Search modes

| Mode | Engine | Best for |
|------|--------|----------|
| `hybrid` (default) | FTS5 + embeddings | Natural language, synonyms, cross-language |
| `keyword` | FTS5 only | Exact codes, prefixes |
| `semantic` | Embeddings only | Conceptual queries ("gallbladder removal") |

Hybrid ranking uses **reciprocal rank fusion (RRF)** to merge keyword and semantic result lists without double-counting layer boosts or producing scores above 100%.

```
rrf_score = Σ 1 / (RRF_K + rank_i)   # RRF_K = 60 by default
```

Each list contributes by position (rank 1, 2, 3…). Keyword ranks come from FTS5 `bm25()` (more negative = better match), converted to a 0–1 score for display only. Semantic results are sorted by cosine similarity before fusion. Curated NLM terms and flagged surgical procedures receive a small layer boost applied after fusion.

## Deployment notes

- The SQLite database (`data/surgical.db`) is built locally and gitignored (~100MB+ with embeddings).
- First `python scripts/build_all.py` run downloads public files and may take 30–60 minutes including semantic indexing.
- Optional: set `YOUTUBE_API_KEY` in `.env` for future API caching.
