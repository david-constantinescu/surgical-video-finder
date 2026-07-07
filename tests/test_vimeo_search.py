"""Tests for Vimeo inline video integration."""

from __future__ import annotations

from unittest.mock import patch

from app.models import CachedVideo
from app.vimeo_search import (
    search_vimeo,
    search_vimeo_official,
    vimeo_inline_enabled,
    vimeo_official_api_enabled,
)


def test_vimeo_official_api_disabled_without_token(monkeypatch):
    monkeypatch.setattr("app.vimeo_search.VIMEO_TOKEN", "")
    assert vimeo_official_api_enabled() is False
    assert search_vimeo_official("appendectomy") == []


def test_vimeo_inline_enabled_without_token(monkeypatch):
    monkeypatch.setattr("app.vimeo_search.VIMEO_TOKEN", "")
    assert vimeo_inline_enabled() is True


def test_search_vimeo_falls_back_to_nokey(monkeypatch):
    monkeypatch.setattr("app.vimeo_search.VIMEO_TOKEN", "")
    sample = [
        CachedVideo(
            title="Demo",
            url="https://vimeo.com/99",
            source="vimeo",
            external_id="99",
            embed_url="https://player.vimeo.com/video/99",
        )
    ]
    with patch("app.vimeo_search.search_vimeo_nokey", return_value=sample):
        assert len(search_vimeo("appendectomy")) == 1


def test_search_vimeo_official_parses_response(monkeypatch):
    monkeypatch.setattr("app.vimeo_search.VIMEO_TOKEN", "test-token")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "uri": "/videos/12345",
                        "name": "Lap Appendectomy",
                        "link": "https://vimeo.com/12345",
                        "pictures": {"sizes": [{"link": "https://img.example/v.jpg"}]},
                        "user": {"name": "Surgery Edu"},
                    }
                ]
            }

    with patch("app.vimeo_search.requests.get", return_value=FakeResponse()):
        videos = search_vimeo_official("appendectomy", max_results=3)

    assert len(videos) == 1
    assert videos[0].external_id == "12345"
    assert videos[0].embed_url == "https://player.vimeo.com/video/12345"
    assert videos[0].channel == "Surgery Edu"
