from __future__ import annotations

from typing import Protocol

from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary


class JobRepository(Protocol):
    def save_raw(self, output_path: str, text: str) -> None:
        ...

    def save_jobs(self, output_path: str, jobs: list[JobPosting] | list[JobSummary]) -> None:
        ...
