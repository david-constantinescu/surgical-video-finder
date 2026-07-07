"""Tests for no-key Vimeo search."""

from __future__ import annotations

from unittest.mock import patch

from app.nokey_vimeo import search_vimeo_nokey


def test_search_vimeo_nokey_parses_search_and_oembed():
    class SearchResponse:
        def raise_for_status(self):
            return None

        @property
        def text(self):
            return '<a href="https://vimeo.com/12345">Lap Appendectomy</a>'

    class OEmbedResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "title": "Lap Appendectomy",
                "url": "https://vimeo.com/12345",
                "thumbnail_url": "https://img.example/v.jpg",
                "author_name": "Surgery Edu",
            }

    with patch(
        "app.nokey_vimeo.requests.get",
        side_effect=[SearchResponse(), OEmbedResponse()],
    ):
        videos = search_vimeo_nokey("appendectomy", max_results=3)

    assert len(videos) == 1
    assert videos[0].external_id == "12345"
    assert videos[0].embed_url == "https://player.vimeo.com/video/12345"
