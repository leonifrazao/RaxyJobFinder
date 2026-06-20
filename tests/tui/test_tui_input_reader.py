from __future__ import annotations

import pytest

from job_search.interfaces.tui.tui_input_reader import TuiInputReader


class Field:
    def __init__(self, value: str) -> None:
        self.value = value


FULL_VALID_FIELDS = {
    "portal": Field("linkedin"),
    "keywords": Field("Python"),
    "location": Field("Brasil"),
    "location_id": Field("106057199"),
    "location_choice": Field("2"),
    "work_type": Field("remote"),
    "applicant_filter": Field("menos de 10 candidaturas"),
    "provider": Field("united-states"),
    "valid_count": Field("1"),
    "jobs_per_proxy": Field("3"),
    "max_count": Field("10"),
    "threads": Field("3"),
    "timeout": Field("15"),
    "detail_timeout": Field("8"),
    "max_jobs": Field("3"),
    "start": Field("0"),
    "details_limit": Field("1"),
    "detail_threads": Field("5"),
    "show_jobs": Field("3"),
    "gd_cookie": Field(""),
    "filters_path": Field("filters/python.json"),
    "jobs_output": Field("jobs.json"),
    "details_output": Field("details.json"),
    "redis_url": Field("redis://localhost:6379/0"),
    "events_channel": Field("raxy:events"),
}


class TestTuiInputReader:
    def test_reads_state_from_fields(self):
        state = TuiInputReader().read(FULL_VALID_FIELDS)

        assert state.portal == "linkedin"
        assert state.keywords == "Python"
        assert state.location == "Brasil"
        assert state.location_id == "106057199"
        assert state.location_choice == "2"
        assert state.work_type == "remote"
        assert state.applicant_filter == "menos de 10 candidaturas"
        assert state.provider == "united-states"
        assert state.valid_count == 1
        assert state.jobs_per_proxy == 3
        assert state.max_count == 10
        assert state.threads == 3
        assert state.timeout == 15.0
        assert state.detail_timeout == 8.0
        assert state.max_jobs == 3
        assert state.start == 0
        assert state.details_limit == 1
        assert state.detail_threads == 5
        assert state.show_jobs == 3
        assert state.gd_cookie == ""
        assert state.filters_path == "filters/python.json"
        assert state.jobs_output == "jobs.json"
        assert state.details_output == "details.json"
        assert state.redis_url == "redis://localhost:6379/0"
        assert state.events_channel == "raxy:events"

    def test_raises_on_invalid_number(self):
        fields = FULL_VALID_FIELDS.copy()
        fields["valid_count"] = Field("oops")

        with pytest.raises(ValueError):
            TuiInputReader().read(fields)

    def test_empty_strings_default_to_empty_string(self):
        fields = FULL_VALID_FIELDS.copy()
        fields["portal"] = Field("")
        fields["keywords"] = Field("")
        fields["location"] = Field("")

        state = TuiInputReader().read(fields)

        assert state.portal == ""
        assert state.keywords == ""
        assert state.location == ""

    def test_empty_numbers_default_to_zero(self):
        fields = FULL_VALID_FIELDS.copy()
        fields["valid_count"] = Field("")
        fields["timeout"] = Field("")
        fields["max_jobs"] = Field("")

        state = TuiInputReader().read(fields)

        assert state.valid_count == 0
        assert state.timeout == 0.0
        assert state.max_jobs == 0

    def test_all_fields_produce_tuistate(self):
        state = TuiInputReader().read(FULL_VALID_FIELDS)
        from dataclasses import fields as dataclass_fields

        tui_fields = {f.name for f in dataclass_fields(state)}
        input_keys = set(FULL_VALID_FIELDS.keys())
        assert input_keys.issubset(tui_fields)
