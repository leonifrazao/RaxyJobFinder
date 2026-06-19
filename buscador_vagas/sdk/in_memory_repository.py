from __future__ import annotations

from buscador_vagas.job_search.domain.job_posting import JobPosting
from buscador_vagas.job_search.domain.job_summary import JobSummary


class InMemoryRepository:
    def __init__(self) -> None:
        self.summaries: list[JobSummary] = []
        self.postings: list[JobPosting] = []

    def save_raw(self, output_path: str, text: str) -> None:
        pass

    def save_jobs(self, output_path: str, jobs: list[JobPosting] | list[JobSummary]) -> None:
        if jobs and isinstance(jobs[0], JobPosting):
            self.postings = list(jobs)
        else:
            self.summaries = list(jobs)
