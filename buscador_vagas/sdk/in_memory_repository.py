from __future__ import annotations

import json
import os
from pathlib import Path

from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary


class InMemoryRepository:
    def __init__(self) -> None:
        self.summaries: list[JobSummary] = []
        self.postings: list[JobPosting] = []

    def save_raw(self, output_path: str, text: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")

    def save_jobs(self, output_path: str, jobs: list[JobPosting] | list[JobSummary]) -> None:
        if jobs and isinstance(jobs[0], JobPosting):
            self.postings = list(jobs)
        else:
            self.summaries = list(jobs)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps([job.to_dict() for job in jobs], ensure_ascii=False, indent=2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
