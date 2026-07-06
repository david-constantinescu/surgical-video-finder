import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH, DATA_DIR, EMBEDDING_MODEL

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS terms (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  kind          TEXT NOT NULL CHECK(kind IN ('diagnosis','procedure')),
  code          TEXT,
  code_system   TEXT,
  primary_name  TEXT NOT NULL,
  consumer_name TEXT,
  layer         TEXT NOT NULL CHECK(layer IN ('curated','comprehensive')),
  specialty     TEXT,
  is_surgical   INTEGER DEFAULT 0,
  complexity    TEXT,
  parent_code   TEXT,
  active        INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS term_translations (
  term_id       INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
  locale        TEXT NOT NULL CHECK(locale IN ('en','ro')),
  primary_name  TEXT NOT NULL,
  consumer_name TEXT,
  UNIQUE(term_id, locale)
);

CREATE TABLE IF NOT EXISTS synonyms (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  term_id  INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
  alias    TEXT NOT NULL,
  locale   TEXT NOT NULL DEFAULT 'en' CHECK(locale IN ('en','ro')),
  source   TEXT
);

CREATE TABLE IF NOT EXISTS term_embeddings (
  term_id    INTEGER PRIMARY KEY REFERENCES terms(id) ON DELETE CASCADE,
  model      TEXT NOT NULL,
  embedding  BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS video_sources (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  slug          TEXT UNIQUE NOT NULL,
  tier          TEXT NOT NULL CHECK(tier IN ('api','search_link','curated_feed')),
  language      TEXT,
  specialty     TEXT,
  base_url      TEXT NOT NULL,
  requires_auth INTEGER DEFAULT 0,
  notes         TEXT
);

CREATE TABLE IF NOT EXISTS video_results (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  term_id       INTEGER REFERENCES terms(id) ON DELETE CASCADE,
  source_id     INTEGER REFERENCES video_sources(id) ON DELETE CASCADE,
  title         TEXT,
  url           TEXT NOT NULL,
  thumbnail_url TEXT,
  language      TEXT,
  fetched_at    TEXT,
  is_cached     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS import_log (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source_name   TEXT NOT NULL,
  version       TEXT,
  imported_at   TEXT NOT NULL DEFAULT (datetime('now')),
  row_count     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_terms_kind ON terms(kind);
CREATE INDEX IF NOT EXISTS idx_terms_code ON terms(code);
CREATE INDEX IF NOT EXISTS idx_terms_layer ON terms(layer);
CREATE INDEX IF NOT EXISTS idx_synonyms_term ON synonyms(term_id);
CREATE INDEX IF NOT EXISTS idx_synonyms_locale ON synonyms(locale);
CREATE INDEX IF NOT EXISTS idx_translations_locale ON term_translations(locale);
"""


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "raw").mkdir(exist_ok=True)
    (DATA_DIR / "embeddings").mkdir(exist_ok=True)


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    ensure_data_dir()
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_session(db_path: Path | None = None):
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    with db_session(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


def log_import(conn: sqlite3.Connection, source_name: str, version: str, row_count: int) -> None:
    conn.execute(
        "INSERT INTO import_log (source_name, version, row_count) VALUES (?, ?, ?)",
        (source_name, version, row_count),
    )


def upsert_en_translation(
    conn: sqlite3.Connection,
    term_id: int,
    primary_name: str,
    consumer_name: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO term_translations (term_id, locale, primary_name, consumer_name)
        VALUES (?, 'en', ?, ?)
        ON CONFLICT(term_id, locale) DO UPDATE SET
          primary_name = excluded.primary_name,
          consumer_name = excluded.consumer_name
        """,
        (term_id, primary_name, consumer_name),
    )


def upsert_ro_translation(
    conn: sqlite3.Connection,
    term_id: int,
    primary_name: str,
    consumer_name: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO term_translations (term_id, locale, primary_name, consumer_name)
        VALUES (?, 'ro', ?, ?)
        ON CONFLICT(term_id, locale) DO UPDATE SET
          primary_name = excluded.primary_name,
          consumer_name = excluded.consumer_name
        """,
        (term_id, primary_name, consumer_name),
    )


def add_synonym(
    conn: sqlite3.Connection,
    term_id: int,
    alias: str,
    locale: str = "en",
    source: str | None = None,
) -> None:
    alias = alias.strip()
    if not alias:
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO synonyms (term_id, alias, locale, source)
        VALUES (?, ?, ?, ?)
        """,
        (term_id, alias, locale, source),
    )


def find_term_by_code(
    conn: sqlite3.Connection,
    code: str,
    code_system: str,
) -> int | None:
    row = conn.execute(
        "SELECT id FROM terms WHERE code = ? AND code_system = ?",
        (code, code_system),
    ).fetchone()
    return row["id"] if row else None


def embedding_model_name() -> str:
    return EMBEDDING_MODEL
