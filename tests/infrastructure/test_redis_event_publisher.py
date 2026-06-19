from __future__ import annotations

import json
from unittest.mock import patch

from redis.exceptions import RedisError

from job_search.application.events import NoopSearchEventPublisher, SearchEvent
from job_search.infrastructure.messaging import build_search_event_publisher
from job_search.infrastructure.messaging.redis_search_event_publisher import RedisSearchEventPublisher


class FakeRedis:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> None:
        self.messages.append((channel, message))


class FailingRedis:
    def __init__(self) -> None:
        self.calls = 0

    def publish(self, channel: str, message: str) -> None:
        self.calls += 1
        raise RedisError("down")


class TestRedisSearchEventPublisher:
    def test_publishes_event_json(self):
        fake = FakeRedis()
        with patch("job_search.infrastructure.messaging.redis_search_event_publisher.Redis.from_url", return_value=fake):
            publisher = RedisSearchEventPublisher(redis_url="redis://localhost:6379/0", channel="raxy:test")

        publisher.publish(SearchEvent(name="job_search_started", message="started", payload={"portal": "linkedin"}))

        channel, message = fake.messages[0]
        assert channel == "raxy:test"
        payload = json.loads(message)
        assert payload["name"] == "job_search_started"
        assert payload["payload"]["portal"] == "linkedin"

    def test_disables_after_redis_error(self):
        fake = FailingRedis()
        with patch("job_search.infrastructure.messaging.redis_search_event_publisher.Redis.from_url", return_value=fake):
            publisher = RedisSearchEventPublisher(redis_url="redis://localhost:6379/0", channel="raxy:test")

        event = SearchEvent(name="event", message="message")
        publisher.publish(event)
        publisher.publish(event)

        assert fake.calls == 1


class TestBuildSearchEventPublisher:
    def test_without_redis_url_returns_noop(self):
        publisher = build_search_event_publisher(None, "raxy:test")

        assert isinstance(publisher, NoopSearchEventPublisher)
