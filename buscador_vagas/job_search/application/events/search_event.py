from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SearchEventName(str, Enum):
    JOB_SEARCH_STARTED = "job_search_started"
    JOB_SEARCH_NO_WORKING_BRIDGE = "job_search_no_working_bridge"
    JOB_SEARCH_NO_JOBS = "job_search_no_jobs"
    JOB_SEARCH_FINISHED = "job_search_finished"
    SEARCH_DATA = "search_data"

    PROXY_PREPARE_STARTED = "proxy_prepare_started"
    PROXY_TESTING = "proxy_testing"
    PROXY_TESTED = "proxy_tested"
    PROXY_VERIFYING = "proxy_verifying"
    PROXY_BRIDGE_VERIFIED = "proxy_bridge_verified"
    PROXY_BRIDGE_FAILED = "proxy_bridge_failed"
    PROXY_NO_WORKING = "proxy_no_working"
    PROXY_NO_BRIDGES = "proxy_no_bridges"
    PROXY_PREPARE_FINISHED = "proxy_prepare_finished"
    BRIDGES_PREPARED = "bridges_prepared"

    LOCATION_TYPEAHEAD_FAILED = "location_typeahead_failed"
    LOCATION_RESOLVED = "location_resolved"
    SEARCH_BRIDGE_ATTEMPT = "search_bridge_attempt"
    SEARCH_BRIDGE_FAILED = "search_bridge_failed"
    SEARCH_BRIDGE_SUCCEEDED = "search_bridge_succeeded"

    DETAIL_STARTED = "detail_started"
    DETAIL_PROGRESS = "detail_progress"
    DETAIL_FAILED = "detail_failed"
    JOB_DETAIL_BRIDGE_FAILED = "job_detail_bridge_failed"
    JOB_DETAIL_FAILED = "job_detail_failed"

    SAVE_STARTED = "save_started"
    SAVE_DETAILS_STARTED = "save_details_started"
    SAVE_FINISHED = "save_finished"
    JOBS_FILTERED = "jobs_filtered"


@dataclass(frozen=True)
class SearchEvent:
    name: str | SearchEventName
    message: str
    level: str = "info"
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value if isinstance(self.name, SearchEventName) else self.name,
            "message": self.message,
            "level": self.level,
            "payload": self.payload,
            "occurred_at": self.occurred_at,
        }
