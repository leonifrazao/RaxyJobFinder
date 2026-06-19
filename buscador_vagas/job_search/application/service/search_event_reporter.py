from __future__ import annotations

from job_search.application.events.noop_search_event_publisher import NoopSearchEventPublisher
from job_search.application.events.search_event import SearchEvent, SearchEventName
from job_search.application.ports import JobBoardAdapter, SearchEventPublisher, SearchEventReporter


class DefaultSearchEventReporter(SearchEventReporter):
    def __init__(self, adapter: JobBoardAdapter, event_publisher: SearchEventPublisher | None = None) -> None:
        self.adapter = adapter
        self.event_publisher = event_publisher or NoopSearchEventPublisher()

    def publish(self, name: str | SearchEventName, message: str, level: str = "info", **payload) -> None:
        event_payload = {"portal": self.adapter.name, **payload}
        self.event_publisher.publish(SearchEvent(name=name, message=message, level=level, payload=event_payload))
