from __future__ import annotations

from typing import Protocol

from job_search.application.events.search_event import SearchEventName


class SearchEventReporter(Protocol):
    def publish(self, name: str | SearchEventName, message: str, level: str = "info", **payload) -> None:
        ...
