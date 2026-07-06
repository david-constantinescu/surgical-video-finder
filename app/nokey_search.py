"""Search YouTube videos without API keys (Piped / Invidious public APIs)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import requests

from app.config import NOKEY_SEARCH_INSTANCES, YOUTUBE_MAX_RESULTS
from app.models import CachedVideo

_YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def _video_id_from_url(url: str) -> str | None:
    if not url:
        return None
    if _YOUTUBE_ID_RE.match(url):
        return url
    parsed = urlparse(url if "://" in url else f"https://youtube.com{url}")
    if parsed.hostname and "youtu" in parsed.hostname:
        if parsed.path == "/watch":
            ids = parse_qs(parsed.query).get("v", [])
            return ids[0] if ids else None
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/")[2] or None
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/")[2] or None
    return None


def _piped_items(payload) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("items") or payload.get("results") or []
    return []


def _parse_piped_item(item: dict) -> CachedVideo | None:
    if item.get("type") not in (None, "stream", "video"):
        return None
    video_id = _video_id_from_url(item.get("url", "")) or item.get("id")
    if not video_id or not _YOUTUBE_ID_RE.match(str(video_id)):
        return None
    thumb = item.get("thumbnail") or item.get("thumbnailUrl")
    if isinstance(thumb, list):
        thumb = thumb[-1] if thumb else None
    title = item.get("title") or item.get("name") or "YouTube video"
    channel = item.get("uploaderName") or item.get("author")
    return CachedVideo(
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        thumbnail_url=thumb,
        source="youtube",
        channel=channel,
        external_id=video_id,
        embed_url=f"https://www.youtube-nocookie.com/embed/{video_id}",
        media_type="video",
        cached=False,
    )


def _parse_invidious_item(item: dict) -> CachedVideo | None:
    video_id = item.get("videoId")
    if not video_id or not _YOUTUBE_ID_RE.match(video_id):
        return None
    thumbs = item.get("videoThumbnails") or []
    thumb = thumbs[-1].get("url") if thumbs else None
    return CachedVideo(
        title=item.get("title") or "YouTube video",
        url=f"https://www.youtube.com/watch?v={video_id}",
        thumbnail_url=thumb,
        source="youtube",
        channel=item.get("author"),
        external_id=video_id,
        embed_url=f"https://www.youtube-nocookie.com/embed/{video_id}",
        media_type="video",
        cached=False,
    )


def _search_piped(base_url: str, query: str, limit: int) -> list[CachedVideo]:
    response = requests.get(
        f"{base_url.rstrip('/')}/search",
        params={"q": query, "filter": "videos"},
        timeout=12,
        headers={"User-Agent": "surgical-video-finder/1.0"},
    )
    response.raise_for_status()
    videos: list[CachedVideo] = []
    for item in _piped_items(response.json()):
        if not isinstance(item, dict):
            continue
        parsed = _parse_piped_item(item)
        if parsed:
            videos.append(parsed)
        if len(videos) >= limit:
            break
    return videos


def _search_invidious(base_url: str, query: str, limit: int) -> list[CachedVideo]:
    response = requests.get(
        f"{base_url.rstrip('/')}/api/v1/search",
        params={"q": query, "type": "video", "sort_by": "relevance"},
        timeout=12,
        headers={"User-Agent": "surgical-video-finder/1.0"},
    )
    response.raise_for_status()
    videos: list[CachedVideo] = []
    for item in response.json():
        if not isinstance(item, dict):
            continue
        parsed = _parse_invidious_item(item)
        if parsed:
            videos.append(parsed)
        if len(videos) >= limit:
            break
    return videos


def search_youtube_nokey(query: str, max_results: int | None = None) -> list[CachedVideo]:
    """Find embeddable YouTube videos via public Piped/Invidious instances (no API key)."""
    limit = max_results or YOUTUBE_MAX_RESULTS
    last_error: Exception | None = None

    for instance in NOKEY_SEARCH_INSTANCES:
        base = instance.strip().rstrip("/")
        if not base:
            continue
        try:
            if "/api/" in base or "invidious" in base:
                videos = _search_invidious(base, query, limit)
            else:
                videos = _search_piped(base, query, limit)
            if videos:
                return videos
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return []
