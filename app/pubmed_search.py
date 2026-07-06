"""PubMed E-utilities search for articles with surgical video content."""

from __future__ import annotations

import sqlite3

import requests

from app.config import INLINE_CACHE_TTL_HOURS, NCBI_CONTACT_EMAIL, PUBMED_MAX_RESULTS
from app.models import CachedVideo, Term
from app.video_cache import fetch_or_cache
from app.video_links import query_for_term

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
SOURCE_SLUG = "pubmed"


def pubmed_api_enabled() -> bool:
    return True


def _pubmed_query(term_query: str) -> str:
    return f'({term_query}) AND (video OR multimedia OR "video abstract")'


def search_pubmed_api(query: str, max_results: int | None = None) -> list[CachedVideo]:
    limit = max_results or PUBMED_MAX_RESULTS
    search = requests.get(
        ESEARCH_URL,
        params={
            "db": "pubmed",
            "term": _pubmed_query(query),
            "retmax": limit,
            "retmode": "json",
            "sort": "relevance",
            "tool": "surgical-video-finder",
            "email": NCBI_CONTACT_EMAIL,
        },
        timeout=15,
    )
    search.raise_for_status()
    ids = search.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    summary = requests.get(
        ESUMMARY_URL,
        params={
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
            "tool": "surgical-video-finder",
            "email": NCBI_CONTACT_EMAIL,
        },
        timeout=15,
    )
    summary.raise_for_status()
    result = summary.json().get("result", {})

    videos: list[CachedVideo] = []
    for pmid in ids:
        item = result.get(pmid, {})
        if not isinstance(item, dict):
            continue
        title = item.get("title") or f"PubMed {pmid}"
        authors = item.get("authors") or []
        channel = authors[0].get("name") if authors else "PubMed"
        videos.append(
            CachedVideo(
                title=title,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                thumbnail_url=None,
                source=SOURCE_SLUG,
                channel=channel,
                external_id=pmid,
                embed_url=None,
                media_type="article",
                cached=False,
            )
        )
    return videos


def get_pubmed_results_for_term(
    conn: sqlite3.Connection,
    term: Term,
    locale: str,
    *,
    force_refresh: bool = False,
) -> list[CachedVideo]:
    query = query_for_term(term, locale, SOURCE_SLUG)
    return fetch_or_cache(
        conn,
        term.id,
        locale,
        SOURCE_SLUG,
        INLINE_CACHE_TTL_HOURS,
        lambda q: search_pubmed_api(q),
        query,
        force_refresh=force_refresh,
    )
