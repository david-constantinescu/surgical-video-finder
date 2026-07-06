# Terminology data sources

All terminology is stored locally in SQLite for fast offline search.

## English sources

| Source | Records (approx.) | Role |
|--------|-------------------|------|
| [NLM Clinical Tables — conditions](https://clinicaltables.nlm.nih.gov/) | ~2,400 | Curated diagnosis names + synonyms |
| [NLM Clinical Tables — procedures](https://clinicaltables.nlm.nih.gov/) | ~280 | Curated major surgery names + synonyms |
| [CDC ICD-10-CM](https://www.cdc.gov/nchs/icd/icd-10-cm/files.html) | ~74,000 | Comprehensive diagnoses |
| [CMS ICD-10-PCS codes file](https://www.cms.gov/medicare/coding-billing/icd-10-codes) | ~79,000 | Comprehensive inpatient procedures |
| [icd-mappings](https://github.com/mpopuri2/icd-mappings) | — | `IS_SURGICAL`, specialty, complexity on PCS codes |

NLM CSV direct downloads are not always available; the build script falls back to the public NLM search API and stores JSON locally.

## Romanian sources

| Source | Role |
|--------|------|
| [icd10.ro](https://www.icd10.ro/) ICD-10-AM Excel (optional) | Official Romanian diagnosis labels |
| [SANT/CNAS ACHI PDF](http://www.sant.ro/) | Romanian procedure nomenclature (~5,000 lines parsed) |
| `data/curated_ro_overrides.csv` | Manual corrections for curated terms |
| `scripts/translate_curated_ro.py` | Glossary-based RO labels for NLM curated rows |

When a Romanian label is missing, the UI shows the English name with an `[EN]` badge. Multilingual semantic search still matches Romanian queries to English ICD rows.

## Licenses

- **CDC / CMS ICD files** — U.S. government public domain.
- **NLM Clinical Tables** — [NLM terms of use](https://clinicaltables.nlm.nih.gov/faq.html).
- **icd-mappings** — MIT License.
- **AMA CPT** — intentionally **not** included (proprietary).

## Rebuilding the database

```bash
source .venv/bin/activate
python scripts/build_all.py
```

Individual steps:

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
python scripts/build_semantic_index.py   # slow; downloads ML model on first run
```

## Schema overview

- `terms` — unified catalog row (kind, code, layer, surgical flags)
- `term_translations` — `en` / `ro` display names per term
- `synonyms` — searchable aliases per locale
- `terms_fts` — FTS5 virtual table (rebuilt by `build_search_index.py`)
- `term_embeddings` — 384-dim vectors (`paraphrase-multilingual-MiniLM-L12-v2`)
- `import_log` — provenance per import step
