"""Vimeo API search with SQLite caching."""

from __future__ import annotations

import re
import sqlite3

import requests

from app.config import INLINE_CACHE_TTL_HOURS, VIMEO_MAX_RESULTS, VIMEO_TOKEN
from app.models import CachedVideo, Term
from app.video_cache import fetch_or_cache, with_embed_urls
from app.video_links import query_for_term

VIMEO_SEARCH_URL = "https://api.vimeo.com/videos"
SOURCE_SLUG = "vimeo"
_VIMEO_ID_RE = re.compile(r"/videos/(\d+)")


def vimeo_api_enabled() -> bool:
    return bool(VIMEO_TOKEN.strip())


def _parse_vimeo_id(uri: str) -> str | None:
    match = _VIMEO_ID_RE.search(uri or "")
    return match.group(1) if match else None


def search_vimeo_api(query: str, max_results: int | None = None) -> list[CachedVideo]:
    if not vimeo_api_enabled():
        return []

    limit = max_results or VIMEO_MAX_RESULTS
    response = requests.get(
        VIMEO_SEARCH_URL,
        params={"query": query, "per_page": limit, "sort": "relevant"},
        headers={"Authorization": f"bearer {VIMEO_TOKEN}"},
        timeout=15,
    )
    response.raise_for_status()

    videos: list[CachedVideo] = []
    for item in response.json().get("data", []):
        video_id = _parse_vimeo_id(item.get("uri", ""))
        if not video_id:
            continue
        pictures = item.get("pictures", {}).get("sizes") or []
        thumb = pictures[-1]["link"] if pictures else None
        user = item.get("user", {})
        videos.append(
            CachedVideo(
                title=item.get("name", ""),
                url=item.get("link") or f"https://vimeo.com/{video_id}",
                thumbnail_url=thumb,
                source=SOURCE_SLUG,
                channel=user.get("name"),
                external_id=video_id,
                embed_url=f"https://player.vimeo.com/video/{video_id}",
                media_type="video",
                cached=False,
            )
        )
    return videos


def get_vimeo_results_for_term(
    conn: sqlite3.Connection,
    term: Term,
    locale: str,
    *,
    force_refresh: bool = False,
) -> list[CachedVideo]:
    if not vimeo_api_enabled():
        return []

    query = query_for_term(term, locale, SOURCE_SLUG)
    videos = fetch_or_cache(
        conn,
        term.id,
        locale,
        SOURCE_SLUG,
        INLINE_CACHE_TTL_HOURS,
        lambda q: search_vimeo_api(q),
        query,
        force_refresh=force_refresh,
    )
    return with_embed_urls(videos)
