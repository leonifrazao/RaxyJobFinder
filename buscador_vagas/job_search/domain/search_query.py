from __future__ import annotations

from dataclasses import dataclass

from .location_option import LocationOption
from .text import clean_text


@dataclass(frozen=True)
class SearchQuery:
    keywords: str
    location: str
    location_id: str | None = None
    work_type: str | None = None
    under_10_applicants: bool = False

    def __post_init__(self) -> None:
        if not clean_text(self.keywords):
            raise ValueError("keywords are required")

    def with_location(self, location: LocationOption) -> "SearchQuery":
        return SearchQuery(self.keywords, location.name, location.id, self.work_type, self.under_10_applicants)
