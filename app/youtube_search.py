"""YouTube inline search — official API when keyed, no-key Piped/Invidious fallback."""

from __future__ import annotations

import sqlite3

import requests

from app.config import INLINE_CACHE_TTL_HOURS, YOUTUBE_API_KEY, YOUTUBE_MAX_RESULTS
from app.models import CachedVideo, Term
from app.nokey_search import search_youtube_nokey
from app.video_cache import fetch_or_cache, with_embed_urls
from app.video_links import query_for_term

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
SOURCE_SLUG = "youtube"


def youtube_official_api_enabled() -> bool:
    return bool(YOUTUBE_API_KEY.strip())


def youtube_inline_enabled() -> bool:
    return True


# Backward-compatible alias
youtube_api_enabled = youtube_official_api_enabled


def search_youtube_official(query: str, max_results: int | None = None) -> list[CachedVideo]:
    if not youtube_official_api_enabled():
        return []

    limit = max_results or YOUTUBE_MAX_RESULTS
    response = requests.get(
        YOUTUBE_SEARCH_URL,
        params={
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": limit,
            "safeSearch": "strict",
            "relevanceLanguage": "en",
            "key": YOUTUBE_API_KEY,
        },
        timeout=15,
    )
    response.raise_for_status()

    videos: list[CachedVideo] = []
    for item in response.json().get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        thumbs = snippet.get("thumbnails", {})
        thumb = (
            thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}
        ).get("url")
        videos.append(
            CachedVideo(
                title=snippet.get("title", ""),
                url=f"https://www.youtube.com/watch?v={video_id}",
                thumbnail_url=thumb,
                source=SOURCE_SLUG,
                channel=snippet.get("channelTitle"),
                external_id=video_id,
                embed_url=f"https://www.youtube-nocookie.com/embed/{video_id}",
                media_type="video",
                cached=False,
            )
        )
    return videos


def search_youtube(query: str, max_results: int | None = None) -> list[CachedVideo]:
    if youtube_official_api_enabled():
        try:
            return search_youtube_official(query, max_results)
        except requests.RequestException:
            pass
    return search_youtube_nokey(query, max_results)


# Backward-compatible name used in tests
search_youtube_api = search_youtube


def get_youtube_results_for_term(
    conn: sqlite3.Connection,
    term: Term,
    locale: str,
    *,
    force_refresh: bool = False,
) -> list[CachedVideo]:
    query = query_for_term(term, locale, SOURCE_SLUG)
    videos = fetch_or_cache(
        conn,
        term.id,
        locale,
        SOURCE_SLUG,
        INLINE_CACHE_TTL_HOURS,
        lambda q: search_youtube(q),
        query,
        force_refresh=force_refresh,
    )
    return with_embed_urls(videos)
