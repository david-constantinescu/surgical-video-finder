"""Search Vimeo videos without API keys (public search + oEmbed metadata)."""

from __future__ import annotations

import re

import requests

from app.config import VIMEO_MAX_RESULTS
from app.models import CachedVideo

_VIMEO_ID_RE = re.compile(r"vimeo\.com/(\d+)")
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; surgical-video-finder/1.0)"}


def _discover_vimeo_ids(query: str, limit: int) -> list[str]:
    response = requests.get(
        "https://vimeo.com/search/page:1",
        params={"q": query},
        headers=_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    ids: list[str] = []
    seen: set[str] = set()
    for match in _VIMEO_ID_RE.finditer(response.text):
        video_id = match.group(1)
        if video_id in seen:
            continue
        seen.add(video_id)
        ids.append(video_id)
        if len(ids) >= limit:
            break
    return ids


def _oembed_video(video_id: str) -> CachedVideo | None:
    url = f"https://vimeo.com/{video_id}"
    try:
        response = requests.get(
            "https://vimeo.com/api/oembed.json",
            params={"url": url},
            headers=_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return CachedVideo(
            title=f"Vimeo video {video_id}",
            url=url,
            source="vimeo",
            external_id=video_id,
            embed_url=f"https://player.vimeo.com/video/{video_id}",
            media_type="video",
            cached=False,
        )

    thumb = data.get("thumbnail_url")
    return CachedVideo(
        title=data.get("title") or f"Vimeo video {video_id}",
        url=data.get("url") or url,
        thumbnail_url=thumb,
        source="vimeo",
        channel=data.get("author_name"),
        external_id=video_id,
        embed_url=f"https://player.vimeo.com/video/{video_id}",
        media_type="video",
        cached=False,
    )


def search_vimeo_nokey(query: str, max_results: int | None = None) -> list[CachedVideo]:
    """Find embeddable Vimeo videos via public search page + oEmbed (no API token)."""
    limit = max_results or VIMEO_MAX_RESULTS
    ids = _discover_vimeo_ids(query, limit)
    videos: list[CachedVideo] = []
    for video_id in ids:
        item = _oembed_video(video_id)
        if item:
            videos.append(item)
    return videos
