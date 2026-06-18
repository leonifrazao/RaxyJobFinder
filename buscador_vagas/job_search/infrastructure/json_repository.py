from __future__ import annotations

import json
from pathlib import Path

from job_search.domain.dtos import JobPosting, JobSummary


class JsonJobRepository:
    def save_raw(self, output_path: str, text: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")

    def save_jobs(self, output_path: str, jobs: list[JobPosting] | list[JobSummary]) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([job.to_dict() for job in jobs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
