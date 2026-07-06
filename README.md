# Surgical Video Finder

A bilingual (**English / Romanian**) web app for surgeons to search pathologies and procedures, build a multi-term case list, and discover operative videos across **46 external platforms**.

Built with **Python (Flask)**, **SQLite**, **HTML/CSS/JS**.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **161,000+ indexed terms** — NLM curated tables + ICD-10-CM + ICD-10-PCS + Romanian ACHI procedures
- **Hybrid search** — FTS5 keyword index + multilingual semantic embeddings (`smart` / `keyword` / `semantic` modes)
- **EN ↔ RO** — UI, API, and search in English or Romanian
- **46 video sources** — YouTube, CSurgeries, JOMI, WebSurg, specialty societies, Romanian hospitals, and more (hyperlink search; no scraping)
- **Local-first** — SQLite database, runs offline after initial build

## Quick start

```bash
git clone https://github.com/YOUR_USER/surgical-video-finder.git
cd surgical-video-finder
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Build database (first run: downloads sources + indexes; 30–60 min with semantic step)
python scripts/build_all.py

# Run the app
python app/server.py
```

Open **http://localhost:5000**

> The database is not committed to git. You must run `build_all.py` after cloning.

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | Install, build, and troubleshooting |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Terminology sources and rebuild steps |
| [docs/VIDEO_SOURCES.md](docs/VIDEO_SOURCES.md) | Full video platform catalog |
| [docs/I18N.md](docs/I18N.md) | English / Romanian internationalization |

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/terms/search?q=&lang=ro&mode=hybrid` | Search terms |
| `GET /api/terms/{id}?lang=ro` | Term detail |
| `POST /api/terms/batch` | `{"ids":[1,2],"lang":"ro"}` |
| `GET /api/videos/links?term_ids=1,2&lang=ro` | Video source links |
| `GET /api/i18n/{lang}` | UI translations |
| `GET /api/health` | DB status |

### Example

```bash
curl "http://localhost:5000/api/terms/search?q=appendectomy&lang=en&mode=hybrid&limit=5"
curl "http://localhost:5000/api/videos/links?term_ids=1,2&lang=ro"
```

## Configuration

Copy `.env.example` to `.env`:

```env
FLASK_PORT=5000
FLASK_DEBUG=0
YOUTUBE_API_KEY=          # optional; Phase 2 video caching
VIMEO_TOKEN=              # optional
```

## Project structure

```
app/              Flask server, search, video links, UI
scripts/          ETL pipeline (download → import → index)
data/             surgical.db (gitignored), raw downloads
docs/             Architecture and source documentation
```

## Ethics & disclaimer

**Educational use only.** Video content is not peer-reviewed or endorsed. External links open third-party sites; users must comply with each platform's terms of service.

## License

MIT — see [LICENSE](LICENSE). ICD/NLM data remain under their respective upstream licenses.
