"""Shared SQLite cache for inline API video/article results."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.db import db_session
from app.models import CachedVideo

SourceFetcher = Callable[[str], list[CachedVideo]]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def source_id(conn: sqlite3.Connection, slug: str) -> int | None:
    row = conn.execute("SELECT id FROM video_sources WHERE slug = ?", (slug,)).fetchone()
    return int(row["id"]) if row else None


def read_cache(
    conn: sqlite3.Connection,
    term_id: int,
    source_slug: str,
    ttl_hours: int,
) -> list[CachedVideo]:
    sid = source_id(conn, source_slug)
    if sid is None:
        return []

    cutoff = (utcnow() - timedelta(hours=ttl_hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """
        SELECT title, url, thumbnail_url, external_id, is_cached
        FROM video_results
        WHERE term_id = ? AND source_id = ? AND fetched_at >= ?
        ORDER BY id
        """,
        (term_id, sid, cutoff),
    ).fetchall()
    return [
        _row_to_cached_video(row, source_slug)
        for row in rows
    ]


def write_cache(
    conn: sqlite3.Connection,
    term_id: int,
    source_slug: str,
    locale: str,
    videos: list[CachedVideo],
) -> None:
    sid = source_id(conn, source_slug)
    if sid is None:
        return

    fetched_at = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "DELETE FROM video_results WHERE term_id = ? AND source_id = ?",
        (term_id, sid),
    )
    for video in videos:
        conn.execute(
            """
            INSERT INTO video_results (
              term_id, source_id, external_id, title, url, thumbnail_url,
              language, fetched_at, is_cached
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                term_id,
                sid,
                video.external_id,
                video.title,
                video.url,
                video.thumbnail_url,
                locale,
                fetched_at,
            ),
        )


def fetch_or_cache(
    conn: sqlite3.Connection,
    term_id: int,
    locale: str,
    source_slug: str,
    ttl_hours: int,
    fetcher: SourceFetcher,
    query: str,
    *,
    force_refresh: bool = False,
    stale_ttl_hours: int | None = None,
) -> list[CachedVideo]:
    if not force_refresh:
        cached = read_cache(conn, term_id, source_slug, ttl_hours)
        if cached:
            return cached

    try:
        videos = fetcher(query)
    except Exception:
        fallback_hours = stale_ttl_hours or ttl_hours * 24 * 30
        return read_cache(conn, term_id, source_slug, fallback_hours)

    if videos:
        with db_session() as write_conn:
            write_cache(write_conn, term_id, source_slug, locale, videos)
        for video in videos:
            video.cached = True
    return videos


def _row_to_cached_video(row: sqlite3.Row, source_slug: str) -> CachedVideo:
    external_id = row["external_id"]
    embed_url = embed_url_for(source_slug, external_id)
    media_type = "article" if source_slug == "pubmed" else "video"
    return CachedVideo(
        title=row["title"] or "",
        url=row["url"],
        thumbnail_url=row["thumbnail_url"],
        source=source_slug,
        external_id=external_id,
        embed_url=embed_url,
        media_type=media_type,
        cached=bool(row["is_cached"]),
    )


def embed_url_for(source_slug: str, external_id: str | None) -> str | None:
    if not external_id:
        return None
    if source_slug == "youtube":
        return f"https://www.youtube-nocookie.com/embed/{external_id}"
    if source_slug == "vimeo":
        return f"https://player.vimeo.com/video/{external_id}"
    return None


def with_embed_urls(videos: list[CachedVideo]) -> list[CachedVideo]:
    for video in videos:
        if video.embed_url is None and video.media_type == "video":
            video.embed_url = embed_url_for(video.source, video.external_id)
    return videos
