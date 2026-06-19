from __future__ import annotations

from job_search.domain.filtering import JobFilterSet


class _CustomFilterRepository:
    def __init__(self, filter_set: JobFilterSet | None = None) -> None:
        self.filter_set = filter_set

    def load(self, filter_path: str | None) -> JobFilterSet:
        if self.filter_set is not None:
            return self.filter_set
        from job_search.infrastructure.persistence.json_job_filter_repository import JsonJobFilterRepository

        return JsonJobFilterRepository().load(filter_path)
