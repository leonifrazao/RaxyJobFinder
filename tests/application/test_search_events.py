from __future__ import annotations

from job_search.application.events import SearchEvent


class TestSearchEvent:
    def test_to_dict(self):
        event = SearchEvent(name="event", message="message", payload={"portal": "linkedin"})

        data = event.to_dict()

        assert data["name"] == "event"
        assert data["message"] == "message"
        assert data["level"] == "info"
        assert data["payload"] == {"portal": "linkedin"}
        assert "occurred_at" in data
