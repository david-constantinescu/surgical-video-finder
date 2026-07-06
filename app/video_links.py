"""Video source URL builder."""

from __future__ import annotations

import sqlite3
from urllib.parse import quote_plus

from app.models import Term, VideoLinkGroup, VideoSourceLink

EN_SUFFIX = "operative video"
RO_SUFFIX = "video operatie"

# Sources whose templates already include search context — do not append suffix twice
_SUFFIX_IN_URL = frozenset({"pubmed", "google_video"})

_PINNED_SLUGS = ("youtube", "google_video", "youtube_ro")

_SPECIALTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cardiothoracic": ("heart", "cardiac", "thoracic", "coronary", "valve", "aortic"),
    "orthopaedic": ("orthop", "fracture", "joint", "knee", "hip", "spine", "arthro"),
    "gi": ("gastro", "colon", "append", "hernia", "bariatric", "laparosc"),
    "urology": ("prostate", "nephro", "bladder", "urolog"),
    "neurosurgery": ("neuro", "brain", "cranial", "spinal"),
    "ophthalmology": ("ophthal", "cataract", "retina", "cornea"),
    "vascular": ("vascular", "artery", "vein", "aneurysm"),
    "hpb": ("hepat", "pancrea", "cholecyst", "biliary"),
    "bariatric": ("bariatric", "gastric bypass", "sleeve"),
    "general": ("appendectomy", "cholecystectomy", "hernia", "mastectomy"),
}


def _infer_specialty(term: Term) -> str | None:
    if term.specialty:
        return term.specialty.lower().split("/")[0].strip()
    text = f"{term.display_name} {term.primary_name}".lower()
    for specialty, keywords in _SPECIALTY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return specialty
    return None


def query_for_term(term: Term, locale: str, slug: str | None = None) -> str:
    return _query_for_term(term, locale, slug)


def _query_for_term(term: Term, locale: str, slug: str | None = None) -> str:
    name = (term.video_query or term.display_name).strip()
    if slug in _SUFFIX_IN_URL:
        return f"{name} chirurgie" if locale == "ro" else name
    if locale == "ro":
        return f"{name} chirurgie {RO_SUFFIX}"
    if term.kind == "diagnosis":
        return f"{name} surgery treatment {EN_SUFFIX}"
    return f"{name} surgery {EN_SUFFIX}"


def _build_url(base_url: str, encoded_query: str) -> str | None:
    if "{query}" not in base_url:
        return None
    return base_url.replace("{query}", encoded_query)


def _filter_sources(
    conn: sqlite3.Connection,
    specialty: str | None,
    locale: str,
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT * FROM video_sources
        ORDER BY
          CASE tier WHEN 'api' THEN 0 WHEN 'search_link' THEN 1 ELSE 2 END,
          CASE language WHEN 'multi' THEN 0 WHEN ? THEN 1 ELSE 2 END,
          name
        """,
        (locale,),
    ).fetchall()

    if not specialty:
        generic = [r for r in rows if not r["specialty"]]
        pinned = [r for r in rows if r["slug"] in _PINNED_SLUGS]
        seen = {r["slug"] for r in pinned}
        result = []
        for r in pinned:
            if r["slug"] not in seen or r in result:
                continue
            result.append(r)
            seen.add(r["slug"])
        for r in generic:
            if r["slug"] not in seen:
                result.append(r)
                seen.add(r["slug"])
        return result[:20] if len(result) >= 8 else rows[:25]

    matched = [
        r for r in rows
        if not r["specialty"] or r["specialty"] == specialty or r["slug"] in _PINNED_SLUGS
    ]
    return matched if len(matched) >= 5 else rows[:25]


def _links_for_term(
    sources: list[sqlite3.Row],
    term: Term,
    locale: str,
) -> list[VideoSourceLink]:
    slug_label = term.display_name
    links: list[VideoSourceLink] = []

    for src in sources:
        base_query = _query_for_term(term, locale, src["slug"])
        encoded = quote_plus(base_query)
        if src["language"] not in (None, "multi", locale) and src["language"] != locale:
            if src["slug"] not in _PINNED_SLUGS:
                continue
        url = _build_url(src["base_url"], encoded)
        if not url:
            continue
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
                term_id=term.id,
                term_name=slug_label,
            )
        )
    return links


def build_video_link_groups(
    conn: sqlite3.Connection,
    terms: list[Term],
    locale: str = "en",
    max_sources_per_term: int = 12,
) -> list[VideoLinkGroup]:
    if not terms:
        return []

    groups: list[VideoLinkGroup] = []
    for term in terms:
        specialty = _infer_specialty(term)
        sources = _filter_sources(conn, specialty, locale)
        links = _links_for_term(sources, term, locale)[:max_sources_per_term]
        if links:
            groups.append(
                VideoLinkGroup(
                    term_id=term.id,
                    term_name=term.display_name,
                    sources=links,
                )
            )
    return groups


def build_video_links(
    conn: sqlite3.Connection,
    terms: list[Term],
    locale: str = "en",
) -> list[VideoSourceLink]:
    """Flat list for backward compatibility — deduped by slug, pinned first."""
    groups = build_video_link_groups(conn, terms, locale)
    seen: set[str] = set()
    flat: list[VideoSourceLink] = []
    for group in groups:
        for link in group.sources:
            key = f"{link.slug}:{link.url}"
            if key in seen:
                continue
            seen.add(key)
            flat.append(link)
    return flat
