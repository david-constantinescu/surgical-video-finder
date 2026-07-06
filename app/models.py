from dataclasses import dataclass, field


@dataclass
class Term:
    id: int
    kind: str
    code: str | None
    code_system: str | None
    primary_name: str
    consumer_name: str | None
    layer: str
    specialty: str | None
    is_surgical: bool
    complexity: str | None
    display_name: str
    locale: str
    synonyms: list[str] = field(default_factory=list)
    score: float | None = None
    fallback_en: bool = False
    fallback_ro: bool = False
    video_query: str = ""


@dataclass
class CachedVideo:
    title: str
    url: str
    source: str
    thumbnail_url: str | None = None
    channel: str | None = None
    external_id: str | None = None
    embed_url: str | None = None
    media_type: str = "video"
    cached: bool = True


@dataclass
class VideoSourceLink:
    name: str
    slug: str
    url: str
    tier: str
    language: str | None
    specialty: str | None
    requires_auth: bool
    notes: str | None = None
    term_id: int | None = None
    term_name: str | None = None


@dataclass
class VideoLinkGroup:
    term_id: int
    term_name: str
    sources: list[VideoSourceLink]
    inline_videos: list[CachedVideo] = field(default_factory=list)
