"""Unified inline results from YouTube, Vimeo, and PubMed."""

from __future__ import annotations

import sqlite3

from app.models import Term, VideoLinkGroup
from app.pubmed_search import get_pubmed_results_for_term, pubmed_api_enabled
from app.vimeo_search import (
    get_vimeo_results_for_term,
    vimeo_inline_enabled,
    vimeo_official_api_enabled,
)
from app.youtube_search import (
    get_youtube_results_for_term,
    youtube_inline_enabled,
    youtube_official_api_enabled,
)


def inline_api_status() -> dict[str, bool]:
    return {
        "youtube": youtube_inline_enabled(),
        "youtube_official_api": youtube_official_api_enabled(),
        "vimeo": vimeo_inline_enabled(),
        "vimeo_official_api": vimeo_official_api_enabled(),
        "pubmed": pubmed_api_enabled(),
        "requires_api_keys": False,
    }


def any_inline_api_enabled() -> bool:
    return True


def enrich_groups_with_inline_videos(
    conn: sqlite3.Connection,
    groups: list[VideoLinkGroup],
    terms: list[Term],
    locale: str,
    *,
    force_refresh: bool = False,
) -> list[VideoLinkGroup]:
    term_map = {term.id: term for term in terms}
    fetchers = (
        (youtube_inline_enabled, get_youtube_results_for_term),
        (vimeo_inline_enabled, get_vimeo_results_for_term),
        (pubmed_api_enabled, get_pubmed_results_for_term),
    )

    for group in groups:
        term = term_map.get(group.term_id)
        if not term:
            continue

        inline: list = []
        replaced_slugs: set[str] = set()
        for enabled, fetch in fetchers:
            if not enabled():
                continue
            try:
                results = fetch(conn, term, locale, force_refresh=force_refresh)
            except Exception:
                continue
            if results:
                inline.extend(results)
                replaced_slugs.add(results[0].source)

        group.inline_videos = inline
        if replaced_slugs:
            group.sources = [
                source for source in group.sources if source.slug not in replaced_slugs
            ]

    return groups


enrich_groups_with_youtube = enrich_groups_with_inline_videos
