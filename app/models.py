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
