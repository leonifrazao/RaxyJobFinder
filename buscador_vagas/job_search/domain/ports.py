from __future__ import annotations

from typing import Any, Protocol

from .dtos import BridgeEndpoint, HttpResponse, JobDetails, JobPosting, JobSummary, LocationOption, SearchQuery, SearchResult
from .filters import JobFilterSet


class HttpClient(Protocol):
    def get(self, bridge_url: str, url: str, timeout: float, *, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        ...

    def post(self, bridge_url: str, url: str, timeout: float, *, json_body: dict[str, Any] | None = None, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        ...


class JobBoardAdapter(Protocol):
    name: str

    def build_search_url(self, query: SearchQuery) -> str:
        ...

    def get_location_options(self, bridge_url: str, location_query: str, timeout: float) -> list[LocationOption]:
        ...

    def search_jobs(self, bridge_url: str, query: SearchQuery, timeout: float, *, max_jobs: int = 0, start: int = 0) -> SearchResult:
        ...

    def fetch_job_details(self, bridge_url: str, job: JobSummary, search_url: str, timeout: float) -> tuple[JobDetails, HttpResponse]:
        ...


class ProxyPool(Protocol):
    def prepare(self, *, sources: list[str], max_count: int, valid_count: int, threads: int, timeout: float, test_url: str) -> list[BridgeEndpoint]:
        ...
 
    def stop(self) -> None:
        ...


class JobRepository(Protocol):
    def save_raw(self, output_path: str, text: str) -> None:
        ...

    def save_jobs(self, output_path: str, jobs: list[JobPosting] | list[JobSummary]) -> None:
        ...


class JobFilterRepository(Protocol):
    def load(self, filter_path: str | None) -> JobFilterSet:
        ...


class JobSearchView(Protocol):
    def info(self, message: str) -> None:
        ...

    def warn(self, message: str) -> None:
        ...

    def error(self, message: str) -> None:
        ...

    def choose_location(self, options: list[LocationOption], selected_index: int | None) -> LocationOption:
        ...

    def show_jobs(self, jobs: list[JobSummary], limit: int) -> None:
        ...

    def show_job_details(self, jobs: list[JobPosting], limit: int) -> None:
        ...
