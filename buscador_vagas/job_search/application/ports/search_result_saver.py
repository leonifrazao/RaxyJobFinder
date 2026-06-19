from __future__ import annotations

from typing import Protocol

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.domain.job_posting import JobPosting


class SearchResultSaverPort(Protocol):
    def save_empty_outputs(self, request: JobSearchRequest) -> None:
        ...

    def save_results(self, request: JobSearchRequest, filtered_jobs: list[JobPosting]) -> None:
        ...
