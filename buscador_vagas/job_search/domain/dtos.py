from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split())


@dataclass(frozen=True)
class BridgeEndpoint:
    index: int
    url: str

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("bridge index must be non-negative")
        if not self.url:
            raise ValueError("bridge url is required")


@dataclass(frozen=True)
class HttpResponse:
    status_code: int | None
    url: str
    headers: dict[str, Any]
    text: str
    cookies: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LocationOption:
    id: str
    name: str
    kind: str = ""
    provider: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("location id is required")
        if not self.name:
            raise ValueError("location name is required")


@dataclass(frozen=True)
class SearchQuery:
    keywords: str
    location: str
    location_id: str | None = None

    def __post_init__(self) -> None:
        if not _clean(self.keywords):
            raise ValueError("keywords are required")

    def with_location(self, location: LocationOption) -> "SearchQuery":
        return SearchQuery(self.keywords, location.name, location.id)


@dataclass(frozen=True)
class JobSummary:
    provider: str
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    listed_at: str = ""
    listed_text: str = ""
    url: str = ""
    company_url: str = ""
    logo_url: str = ""
    provider_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _clean(self.title) and not self.url:
            raise ValueError("job summary requires title or url")

    def to_dict(self) -> dict[str, Any]:
        data = {
            "provider": self.provider,
            "job_id": self.external_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "listed_at": self.listed_at,
            "listed_text": self.listed_text,
            "url": self.url,
            "company_url": self.company_url,
            "logo_url": self.logo_url,
        }
        data.update(self.provider_data)
        return data


@dataclass(frozen=True)
class JobDetails:
    title: str = ""
    company: str = ""
    company_url: str = ""
    location: str = ""
    posted_text: str = ""
    applicants_text: str = ""
    description: str = ""
    criteria: dict[str, str] = field(default_factory=dict)
    apply_text: str = ""
    url: str = ""
    logo_url: str = ""
    provider_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "detail_title": self.title,
            "detail_company": self.company,
            "detail_company_url": self.company_url,
            "detail_location": self.location,
            "detail_posted_text": self.posted_text,
            "detail_applicants_text": self.applicants_text,
            "description": self.description,
            "criteria": self.criteria,
            "apply_text": self.apply_text,
            "detail_url": self.url,
            "detail_logo_url": self.logo_url,
        }
        data.update(self.provider_data)
        return data


@dataclass(frozen=True)
class JobPosting:
    summary: JobSummary
    details: JobDetails | None = None
    detail_status_code: int | None = None
    detail_html_size: int = 0
    detail_bridge_index: int | None = None
    detail_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self.summary.to_dict()
        if self.details:
            data.update(self.details.to_dict())
        if self.detail_status_code is not None:
            data["detail_status_code"] = self.detail_status_code
        if self.detail_html_size:
            data["detail_html_size"] = self.detail_html_size
        if self.detail_bridge_index is not None:
            data["detail_bridge_index"] = self.detail_bridge_index
        if self.detail_error:
            data["detail_error"] = self.detail_error
        return data


@dataclass(frozen=True)
class SearchResult:
    query: SearchQuery
    search_url: str
    response: HttpResponse
    jobs: list[JobSummary]
