from __future__ import annotations

from job_search.application.events.noop_search_event_publisher import NoopSearchEventPublisher
from job_search.application.ports.search_event_publisher import SearchEventPublisher
from job_search.infrastructure.messaging.redis_search_event_publisher import RedisSearchEventPublisher


def build_search_event_publisher(redis_url: str | None, channel: str | None) -> SearchEventPublisher:
    if not redis_url:
        return NoopSearchEventPublisher()
    return RedisSearchEventPublisher(redis_url=redis_url, channel=channel or "raxy:events")
