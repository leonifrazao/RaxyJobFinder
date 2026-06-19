from __future__ import annotations

from typing import Protocol

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.domain.detailing import JobDetailingSession
from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.domain.proxy import BridgeEndpoint


class JobDetailing(Protocol):
    def enrich_jobs(
        self,
        jobs: list[JobSummary],
        bridges: list[BridgeEndpoint],
        search_url: str,
        request: JobSearchRequest,
    ) -> list[JobPosting]:
        ...

    def detail_one_job(
        self,
        session: JobDetailingSession,
        job: JobSummary,
        job_offset: int,
        search_url: str,
        detail_timeout: float,
    ) -> JobPosting:
        ...
