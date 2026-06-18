from __future__ import annotations

import json
from pathlib import Path

from job_search.domain.filters import JobFilterSet


class JsonJobFilterRepository:
    def load(self, filter_path: str | None) -> JobFilterSet:
        if not filter_path:
            return JobFilterSet.accept_all()
        path = Path(filter_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return JobFilterSet.from_dict(data)
