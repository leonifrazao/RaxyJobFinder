from __future__ import annotations

import json
from collections.abc import Callable
from threading import Event
from typing import Any

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

from job_search.application.ports import SearchEventSubscriber


class RedisSearchEventSubscriber(SearchEventSubscriber):
    def __init__(self, *, redis_url: str, channel: str, socket_timeout: float = 0.5) -> None:
        self.channel = channel
        self._client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=socket_timeout,
            socket_timeout=socket_timeout,
        )

    def listen(self, stop_event: Event, handler: Callable[[dict[str, Any]], None]) -> None:
        pubsub = None
        try:
            pubsub = self._client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(self.channel)
            while not stop_event.is_set():
                message = pubsub.get_message(timeout=0.2)
                if message is None or message.get("type") != "message":
                    continue
                handler(json.loads(str(message.get("data") or "{}")))
        except (RedisError, json.JSONDecodeError) as exc:
            logger.bind(component="redis_event_subscriber", channel=self.channel, error=str(exc)).warning("redis_subscribe_stopped")
        finally:
            if pubsub is not None:
                try:
                    pubsub.close()
                except Exception:
                    pass
