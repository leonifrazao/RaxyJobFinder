from __future__ import annotations

from typing import Protocol

from job_search.application.events.search_event import SearchEvent


class SearchEventPublisher(Protocol):
    def publish(self, event: SearchEvent) -> None:
        ...
