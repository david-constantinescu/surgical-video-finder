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

# Phase 2: YouTube Data API / Vimeo — not used in Phase 1 hyperlink-only mode
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
VIMEO_TOKEN = os.getenv("VIMEO_TOKEN", "")

FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

SUPPORTED_LOCALES = ("en", "ro")
DEFAULT_LOCALE = "en"

RRF_K = 60
