from __future__ import annotations

from typing import Protocol

from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.domain.job_details import JobDetails
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption
from job_search.domain.search_query import SearchQuery


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
