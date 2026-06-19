from __future__ import annotations

from typing import Protocol

from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption


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
