from __future__ import annotations

from typing import Protocol

from job_search.application.dto.input.job_search_request import JobSearchRequest


class JobSearchUseCase(Protocol):
    def run(self, request: JobSearchRequest) -> int:
        ...
