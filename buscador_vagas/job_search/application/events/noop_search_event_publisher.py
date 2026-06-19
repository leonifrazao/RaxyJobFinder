from __future__ import annotations

from job_search.application.events.search_event import SearchEvent


class NoopSearchEventPublisher:
    def publish(self, event: SearchEvent) -> None:
        pass
