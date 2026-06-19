from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .job_details import JobDetails
from .job_summary import JobSummary


@dataclass(frozen=True)
class JobPosting:
    summary: JobSummary
    details: JobDetails | None = None
    detail_status_code: int | None = None
    detail_html_size: int = 0
    detail_bridge_index: int | None = None
    detail_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self.summary.to_dict()
        if self.details:
            data.update(self.details.to_dict())
        if self.detail_status_code is not None:
            data["detail_status_code"] = self.detail_status_code
        if self.detail_html_size:
            data["detail_html_size"] = self.detail_html_size
        if self.detail_bridge_index is not None:
            data["detail_bridge_index"] = self.detail_bridge_index
        if self.detail_error:
            data["detail_error"] = self.detail_error
        return data
