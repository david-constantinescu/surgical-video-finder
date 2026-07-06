"""Tests for YouTube inline video integration."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.db import SCHEMA_SQL
from app.inline_videos import enrich_groups_with_inline_videos
from app.models import CachedVideo, Term
from app.video_links import build_video_link_groups
from app.youtube_search import get_youtube_results_for_term


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    connection.execute(
        """
        INSERT INTO video_sources (name, slug, tier, language, base_url, requires_auth)
        VALUES ('YouTube', 'youtube', 'api', 'multi', 'https://youtube.com/results?search_query={query}', 0)
        """
    )
    connection.execute(
        """
        INSERT INTO terms (id, kind, primary_name, layer, is_surgical, active)
        VALUES (1, 'procedure', 'Appendectomy', 'curated', 1, 1)
        """
    )
    connection.commit()
    yield connection
    connection.close()


def _term() -> Term:
    return Term(
        id=1,
        kind="procedure",
        code=None,
        code_system="NLM",
        primary_name="Appendectomy",
        consumer_name=None,
        layer="curated",
        specialty="gi",
        is_surgical=True,
        complexity=None,
        display_name="Appendectomy",
        locale="en",
        video_query="Appendectomy",
    )


def test_youtube_official_api_disabled_without_key(monkeypatch):
    monkeypatch.setattr("app.youtube_search.YOUTUBE_API_KEY", "")
    from app.youtube_search import search_youtube_official, youtube_official_api_enabled

    assert youtube_official_api_enabled() is False
    assert search_youtube_official("appendectomy") == []


def test_search_youtube_falls_back_to_nokey(monkeypatch):
    monkeypatch.setattr("app.youtube_search.YOUTUBE_API_KEY", "")
    from app.models import CachedVideo
    from app.youtube_search import search_youtube

    sample = [
        CachedVideo(
            title="Demo",
            url="https://www.youtube.com/watch?v=abc",
            source="youtube",
            external_id="abc",
            embed_url="https://www.youtube-nocookie.com/embed/abc",
        )
    ]
    with patch("app.youtube_search.search_youtube_nokey", return_value=sample):
        assert len(search_youtube("appendectomy")) == 1


def test_search_youtube_official_parses_response(monkeypatch):
    monkeypatch.setattr("app.youtube_search.YOUTUBE_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "items": [
                    {
                        "id": {"videoId": "abc123"},
                        "snippet": {
                            "title": "Laparoscopic Appendectomy",
                            "channelTitle": "Surgery Channel",
                            "thumbnails": {"medium": {"url": "https://img.example/thumb.jpg"}},
                        },
                    }
                ]
            }

    with patch("app.youtube_search.requests.get", return_value=FakeResponse()):
        from app.youtube_search import search_youtube_official

        videos = search_youtube_official("appendectomy surgery", max_results=3)

    assert len(videos) == 1
    assert videos[0].external_id == "abc123"
    assert videos[0].embed_url == "https://www.youtube-nocookie.com/embed/abc123"
    assert videos[0].thumbnail_url == "https://img.example/thumb.jpg"


def test_get_youtube_results_caches_in_db(conn, monkeypatch):
    monkeypatch.setattr("app.youtube_search.YOUTUBE_API_KEY", "test-key")

    @contextmanager
    def _test_db_session(db_path=None):
        yield conn

    monkeypatch.setattr("app.video_cache.db_session", _test_db_session)

    sample = [
        CachedVideo(
            title="Appendectomy demo",
            url="https://www.youtube.com/watch?v=xyz",
            thumbnail_url="https://img.example/x.jpg",
            source="youtube",
            channel="Demo",
            external_id="xyz",
            embed_url="https://www.youtube.com/embed/xyz",
        )
    ]

    with patch("app.youtube_search.search_youtube", return_value=sample):
        first = get_youtube_results_for_term(conn, _term(), "en")
        assert len(first) == 1
        row = conn.execute("SELECT COUNT(*) AS c FROM video_results").fetchone()["c"]
        assert row == 1

        with patch("app.youtube_search.search_youtube") as api_mock:
            second = get_youtube_results_for_term(conn, _term(), "en")
            api_mock.assert_not_called()
        assert second[0].title == "Appendectomy demo"


def test_enrich_groups_removes_youtube_hyperlink(conn, monkeypatch):
    monkeypatch.setattr("app.youtube_search.YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr("app.vimeo_search.VIMEO_TOKEN", "")
    term = _term()
    groups = build_video_link_groups(conn, [term], "en")
    assert any(s.slug == "youtube" for g in groups for s in g.sources)

    with patch(
        "app.inline_videos.get_youtube_results_for_term",
        return_value=[
            CachedVideo(
                title="Video",
                url="https://www.youtube.com/watch?v=1",
                thumbnail_url=None,
                source="youtube",
                external_id="1",
                embed_url="https://www.youtube.com/embed/1",
            )
        ],
    ), patch("app.inline_videos.get_pubmed_results_for_term", return_value=[]):
        enrich_groups_with_inline_videos(conn, groups, [term], "en")

    assert groups[0].inline_videos
    assert not any(s.slug == "youtube" for s in groups[0].sources)
