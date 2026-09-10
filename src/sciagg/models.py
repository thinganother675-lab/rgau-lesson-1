"""Source-preserving domain records. JSON serialization uses dataclasses.asdict."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Provenance:
    source: str
    external_id: str = ""
    url: str = ""
    retrieved_at: str = field(default_factory=utc_now)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Metric:
    kind: str
    value: int | float | str | None
    source: str
    retrieved_at: str = field(default_factory=utc_now)
    year: int | None = None
    category: str | None = None
    scope: str = "source"


@dataclass
class Author:
    id: str = ""
    name: str = ""
    identifiers: dict[str, str] = field(default_factory=dict)
    variants: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    dois: list[str] = field(default_factory=list)
    coauthors: list[str] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)


@dataclass
class Publication:
    id: str = ""
    title: str = ""
    doi: str | None = None
    year: int | None = None
    authors: list[Author] = field(default_factory=list)
    issns: list[str] = field(default_factory=list)
    journal: str = ""
    alternative_titles: list[str] = field(default_factory=list)
    source_ids: dict[str, str] = field(default_factory=dict)
    citations: list[Metric] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Journal:
    issns: list[str] = field(default_factory=list)
    title: str = ""
    classifications: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
