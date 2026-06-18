from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .dtos import BridgeEndpoint, HttpResponse, JobDetails, JobPosting, JobSummary


@dataclass
class JobDetailingSession:
    jobs: list[JobSummary]
    bridges: list[BridgeEndpoint]
    jobs_per_proxy: int
    detail_limit: int = 0
    blocked_bridge_indexes: set[int] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.bridges:
            raise ValueError("at least one bridge is required")
        self.jobs_per_proxy = max(1, self.jobs_per_proxy)

    @property
    def jobs_to_detail(self) -> list[JobSummary]:
        if self.detail_limit <= 0:
            return self.jobs
        return self.jobs[:self.detail_limit]

    @property
    def untouched_jobs(self) -> list[JobSummary]:
        if self.detail_limit <= 0:
            return []
        return self.jobs[self.detail_limit:]

    def bridge_candidates_for(self, job_offset: int) -> list[BridgeEndpoint]:
        if job_offset < 0:
            raise ValueError("job offset must be non-negative")
        primary_position = (job_offset // self.jobs_per_proxy) % len(self.bridges)
        ordered = [self.bridges[(primary_position + offset) % len(self.bridges)] for offset in range(len(self.bridges))]
        with self._lock:
            available = [bridge for bridge in ordered if bridge.index not in self.blocked_bridge_indexes]
        return available or ordered

    def mark_bridge_failed(self, bridge: BridgeEndpoint) -> None:
        with self._lock:
            self.blocked_bridge_indexes.add(bridge.index)

    def missing_external_id(self, job: JobSummary) -> JobPosting:
        return JobPosting(summary=job, detail_error="job_id ausente")

    def successful_detail(self, job: JobSummary, details: JobDetails, response: HttpResponse, bridge: BridgeEndpoint) -> JobPosting:
        return JobPosting(
            summary=job,
            details=details,
            detail_status_code=response.status_code,
            detail_html_size=len(response.text),
            detail_bridge_index=bridge.index,
        )

    def failed_detail(self, job: JobSummary, error: str) -> JobPosting:
        return JobPosting(summary=job, detail_error=error)

    def unprocessed_postings(self) -> list[JobPosting]:
        return [JobPosting(summary=job) for job in self.untouched_jobs]
