import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "surgical.db"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 output size

# Phase 2: inline video — works without API keys by default (Piped/Invidious + PubMed).
# Optional YOUTUBE_API_KEY / VIMEO_TOKEN improve reliability when set.
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
VIMEO_TOKEN = os.getenv("VIMEO_TOKEN", "")
NCBI_CONTACT_EMAIL = os.getenv("NCBI_CONTACT_EMAIL", "dev@localhost")
_default_nokey = "https://pipedapi.kavin.rocks,https://pipedapi.adminforge.de"
NOKEY_SEARCH_INSTANCES = [
    u.strip() for u in os.getenv("NOKEY_SEARCH_INSTANCES", _default_nokey).split(",") if u.strip()
]
INLINE_CACHE_TTL_HOURS = int(os.getenv("INLINE_CACHE_TTL_HOURS", "168"))
YOUTUBE_MAX_RESULTS = min(int(os.getenv("YOUTUBE_MAX_RESULTS", "8")), 25)
VIMEO_MAX_RESULTS = min(int(os.getenv("VIMEO_MAX_RESULTS", "6")), 25)
PUBMED_MAX_RESULTS = min(int(os.getenv("PUBMED_MAX_RESULTS", "6")), 25)
# Legacy alias
YOUTUBE_CACHE_TTL_HOURS = INLINE_CACHE_TTL_HOURS

SEMANTIC_MIN_SIMILARITY = float(os.getenv("SEMANTIC_MIN_SIMILARITY", "0.4"))

FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

SUPPORTED_LOCALES = ("en", "ro")
DEFAULT_LOCALE = "en"

RRF_K = 60
