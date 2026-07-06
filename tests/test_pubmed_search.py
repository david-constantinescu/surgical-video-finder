"""Tests for PubMed inline article integration."""

from __future__ import annotations

from unittest.mock import patch

from app.pubmed_search import search_pubmed_api


def test_search_pubmed_api_parses_response():
    class SearchResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"esearchresult": {"idlist": ["12345"]}}

    class SummaryResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "result": {
                    "12345": {
                        "title": "Laparoscopic appendectomy video review",
                        "authors": [{"name": "Smith J"}],
                    }
                }
            }

    with patch("app.pubmed_search.requests.get", side_effect=[SearchResponse(), SummaryResponse()]):
        articles = search_pubmed_api("appendectomy", max_results=3)

    assert len(articles) == 1
    assert articles[0].media_type == "article"
    assert articles[0].external_id == "12345"
    assert "12345" in articles[0].url
    assert articles[0].embed_url is None
