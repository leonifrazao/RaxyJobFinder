from __future__ import annotations

import pytest

from job_search.interfaces.tui.tui_input_reader import TuiInputReader


class Field:
    def __init__(self, value: str) -> None:
        self.value = value


class TestTuiInputReader:
    def test_reads_state_from_fields(self):
        fields = {
            "portal": Field("linkedin"),
            "keywords": Field("Python"),
            "location": Field("Brasil"),
            "provider": Field("united-states"),
            "valid_count": Field("1"),
            "max_count": Field("10"),
            "threads": Field("3"),
            "timeout": Field("15"),
            "detail_timeout": Field("8"),
            "max_jobs": Field("3"),
            "details_limit": Field("1"),
            "detail_threads": Field("5"),
            "show_jobs": Field("3"),
            "jobs_output": Field("jobs.json"),
            "details_output": Field("details.json"),
            "redis_url": Field("redis://localhost:6379/0"),
            "events_channel": Field("raxy:events"),
        }

        state = TuiInputReader().read(fields)

        assert state.portal == "linkedin"
        assert state.valid_count == 1
        assert state.timeout == 15.0
        assert state.jobs_output == "jobs.json"
        assert state.redis_url == "redis://localhost:6379/0"
        assert state.events_channel == "raxy:events"

    def test_raises_on_invalid_number(self):
        fields = {
            "portal": Field("linkedin"),
            "keywords": Field("Python"),
            "location": Field("Brasil"),
            "provider": Field("united-states"),
            "valid_count": Field("oops"),
            "max_count": Field("10"),
            "threads": Field("3"),
            "timeout": Field("15"),
            "detail_timeout": Field("8"),
            "max_jobs": Field("3"),
            "details_limit": Field("1"),
            "detail_threads": Field("5"),
            "show_jobs": Field("3"),
            "jobs_output": Field("jobs.json"),
            "details_output": Field("details.json"),
            "redis_url": Field("redis://localhost:6379/0"),
            "events_channel": Field("raxy:events"),
        }

        with pytest.raises(ValueError):
            TuiInputReader().read(fields)
