"""Video source URL builder."""

from __future__ import annotations

import sqlite3
from urllib.parse import quote_plus

from app.models import Term, VideoSourceLink

EN_SUFFIX = "surgery operative video"
RO_SUFFIX = "chirurgie operatie video"


def _query_for_term(term: Term, locale: str) -> str:
    name = term.display_name
    if locale == "ro":
        return f"{name} {RO_SUFFIX}"
    return f"{name} {EN_SUFFIX}"


def _combined_query(terms: list[Term], locale: str) -> str:
    names = [t.display_name for t in terms[:5]]
    joined = " ".join(names)
    suffix = RO_SUFFIX if locale == "ro" else EN_SUFFIX
    return f"{joined} {suffix}"


def _filter_sources(conn: sqlite3.Connection, specialty: str | None) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT * FROM video_sources
        ORDER BY
          CASE tier WHEN 'api' THEN 0 WHEN 'search_link' THEN 1 ELSE 2 END,
          CASE language WHEN 'multi' THEN 0 WHEN 'en' THEN 1 ELSE 2 END,
          name
        """
    ).fetchall()

    if specialty:
        matched = [r for r in rows if not r["specialty"] or r["specialty"] == specialty]
        if len(matched) >= 10:
            return matched
    return rows


def build_video_links(
    conn: sqlite3.Connection,
    terms: list[Term],
    locale: str = "en",
) -> list[VideoSourceLink]:
    if not terms:
        return []

    specialty = next((t.specialty for t in terms if t.specialty), None)
    sources = _filter_sources(conn, specialty)
    query = _combined_query(terms, locale)
    encoded = quote_plus(query)

    links: list[VideoSourceLink] = []
    for src in sources:
        url = src["base_url"].replace("{query}", encoded)
        links.append(
            VideoSourceLink(
                name=src["name"],
                slug=src["slug"],
                url=url,
                tier=src["tier"],
                language=src["language"],
                specialty=src["specialty"],
                requires_auth=bool(src["requires_auth"]),
                notes=src["notes"],
            )
        )
    return links


def build_per_term_links(
    conn: sqlite3.Connection,
    term: Term,
    locale: str = "en",
    max_sources: int = 15,
) -> list[VideoSourceLink]:
    all_links = build_video_links(conn, [term], locale)
    return all_links[:max_sources]
