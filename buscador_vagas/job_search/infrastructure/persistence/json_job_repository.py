from __future__ import annotations

import json
from pathlib import Path

from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary


SUMMARY_OUTPUT_FIELDS = (
    "provider",
    "job_id",
    "title",
    "company",
    "location",
    "listed_at",
    "listed_text",
    "url",
    "company_url",
    "logo_url",
    "modalidade",
)

DETAIL_OUTPUT_FIELDS = (
    "detail_title",
    "detail_company",
    "detail_company_url",
    "detail_location",
    "detail_posted_text",
    "detail_applicants_text",
    "description",
    "criteria",
    "apply_text",
    "detail_url",
    "detail_logo_url",
    "detail_status_code",
    "detail_html_size",
    "detail_bridge_index",
)


class JsonJobRepository:
    def save_raw(self, output_path: str, text: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")

    def save_jobs(self, output_path: str, jobs: list[JobPosting] | list[JobSummary]) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([self._to_output_dict(job) for job in jobs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _to_output_dict(self, job: JobPosting | JobSummary) -> dict[str, object]:
        data = job.to_dict()
        fields = SUMMARY_OUTPUT_FIELDS + DETAIL_OUTPUT_FIELDS if isinstance(job, JobPosting) else SUMMARY_OUTPUT_FIELDS
        return {field: data.get(field, self._default_value(field)) for field in fields}

    @staticmethod
    def _default_value(field: str) -> object:
        if field == "criteria":
            return {}
        if field in {"detail_status_code", "detail_html_size", "detail_bridge_index"}:
            return None
        return ""
