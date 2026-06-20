from __future__ import annotations

from dataclasses import dataclass

from .location_option import LocationOption
from .text import clean_text

APPLICANT_FILTER_NORMAL = "normal"
APPLICANT_FILTER_UNDER_10 = "menos de 10 candidaturas"
APPLICANT_FILTERS = (APPLICANT_FILTER_NORMAL, APPLICANT_FILTER_UNDER_10)


@dataclass(frozen=True)
class SearchQuery:
    keywords: str
    location: str
    location_id: str | None = None
    work_type: str | None = None
    applicant_filter: str | None = APPLICANT_FILTER_NORMAL

    def __post_init__(self) -> None:
        if not clean_text(self.keywords):
            raise ValueError("keywords are required")
        if self.applicant_filter and self.applicant_filter not in APPLICANT_FILTERS:
            raise ValueError("applicant_filter must be normal or menos de 10 candidaturas")

    def with_location(self, location: LocationOption) -> "SearchQuery":
        return SearchQuery(self.keywords, location.name, location.id, self.work_type, self.applicant_filter)
