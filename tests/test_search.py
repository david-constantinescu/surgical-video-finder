"""Tests for search helpers and API."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from app.search import (
    SemanticIndexNotReady,
    _bm25_to_score,
    _display_name,
    _sanitize_fts_query,
    _strip_diacritics,
    semantic_search,
)


def test_strip_diacritics():
    assert _strip_diacritics("apendicită") == "apendicita"


def test_sanitize_fts_query_strips_diacritics():
    q = _sanitize_fts_query("apendicită")
    assert "apendicita" in q


def test_bm25_negative_rank_scores_higher_for_better_matches():
    good = _bm25_to_score(-5.0)
    bad = _bm25_to_score(10.0)
    assert good > bad


def test_display_name_en_marks_achi_as_fallback_ro():
    row = {
        "id": 1, "kind": "procedure", "code": "123", "code_system": "ACHI-RO",
        "primary_name": "Apendicectomia", "consumer_name": None,
        "layer": "comprehensive", "specialty": None, "is_surgical": 1, "complexity": None,
        "en_name": "Apendicectomia", "en_consumer": None,
        "ro_name": "Apendicectomia", "ro_consumer": None,
        "aliases_en": None, "aliases_ro": None,
    }
    display, fb_en, fb_ro = _display_name(row, "en")
    assert fb_ro is True
    assert display == "Apendicectomia"


def test_semantic_search_raises_when_index_missing():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE term_embeddings (term_id INTEGER, embedding BLOB)")
    with patch("app.search._load_embedding_cache", return_value=(None, None, None)):
        with pytest.raises(SemanticIndexNotReady):
            semantic_search(conn, "appendectomy", "en", None, 5)
