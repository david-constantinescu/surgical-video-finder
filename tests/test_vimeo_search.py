"""Tests for Vimeo inline video integration."""

from __future__ import annotations

from unittest.mock import patch

from app.vimeo_search import search_vimeo_api, vimeo_api_enabled


def test_vimeo_api_disabled_without_token(monkeypatch):
    monkeypatch.setattr("app.vimeo_search.VIMEO_TOKEN", "")
    assert vimeo_api_enabled() is False
    assert search_vimeo_api("appendectomy") == []


def test_search_vimeo_api_parses_response(monkeypatch):
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
        videos = search_vimeo_api("appendectomy", max_results=3)

    assert len(videos) == 1
    assert videos[0].external_id == "12345"
    assert videos[0].embed_url == "https://player.vimeo.com/video/12345"
    assert videos[0].channel == "Surgery Edu"
