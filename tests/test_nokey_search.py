"""Tests for no-key YouTube search."""

from __future__ import annotations

from unittest.mock import patch

from app.nokey_search import search_youtube_nokey


def test_search_youtube_nokey_parses_piped_response():
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "items": [
                    {
                        "type": "stream",
                        "title": "Lap Appendectomy",
                        "url": "/watch?v=dQw4w9WgXcQ",
                        "thumbnail": "https://img.example/t.jpg",
                        "uploaderName": "Surgery Edu",
                    }
                ]
            }

    with patch("app.nokey_search.requests.get", return_value=FakeResponse()):
        videos = search_youtube_nokey("appendectomy", max_results=3)

    assert len(videos) == 1
    assert videos[0].external_id == "dQw4w9WgXcQ"
    assert "youtube-nocookie.com/embed" in (videos[0].embed_url or "")
