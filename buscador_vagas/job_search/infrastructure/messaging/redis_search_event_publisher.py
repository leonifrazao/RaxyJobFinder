from __future__ import annotations

import json

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

from job_search.application.events.search_event import SearchEvent


class RedisSearchEventPublisher:
    def __init__(self, *, redis_url: str, channel: str, socket_timeout: float = 0.2) -> None:
        self.channel = channel
        self._client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=socket_timeout,
            socket_timeout=socket_timeout,
        )
        self._available = True

    def publish(self, event: SearchEvent) -> None:
        if not self._available:
            return
        try:
            self._client.publish(self.channel, json.dumps(event.to_dict(), ensure_ascii=False))
        except RedisError as exc:
            self._available = False
            logger.bind(component="redis_event_publisher", channel=self.channel, error=str(exc)).warning("redis_publish_disabled")
