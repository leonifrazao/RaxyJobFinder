from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobSearchRequest:
    proxy_sources: list[str]
    keywords: str
    location: str
    location_id: str | None
    location_choice: int | None
    valid_count: int
    jobs_per_proxy: int
    max_count: int
    threads: int
    timeout: float
    detail_timeout: float
    jobs_output: str
    details_output: str
    filters_path: str | None
    details_limit: int
    show_jobs: int
    start: int = 0
    max_jobs: int = 0
    detail_threads: int = 5
    work_type: str | None = None
    under_10_applicants: bool = False
