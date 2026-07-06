import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "surgical.db"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
VIMEO_TOKEN = os.getenv("VIMEO_TOKEN", "")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

SUPPORTED_LOCALES = ("en", "ro")
DEFAULT_LOCALE = "en"
