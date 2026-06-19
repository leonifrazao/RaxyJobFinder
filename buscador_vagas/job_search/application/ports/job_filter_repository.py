from __future__ import annotations

from typing import Protocol

from job_search.domain.filtering import JobFilterSet


class JobFilterRepository(Protocol):
    def load(self, filter_path: str | None) -> JobFilterSet:
        ...
