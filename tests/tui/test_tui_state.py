from __future__ import annotations

from dataclasses import fields

from job_search.interfaces.tui.tui_state import TuiState


class TestTuiState:
    def test_default_values(self):
        state = TuiState()

        assert state.portal == "linkedin"
        assert state.keywords == "Python"
        assert state.location == "Brasil"
        assert state.location_id == ""
        assert state.location_choice == "1"
        assert state.valid_count == 25
        assert state.jobs_per_proxy == 5
        assert state.max_count == 177
        assert state.threads == 8
        assert state.timeout == 15.0
        assert state.detail_timeout == 15.0
        assert state.max_jobs == 0
        assert state.start == 0
        assert state.details_limit == 0
        assert state.detail_threads == 5
        assert state.show_jobs == 10
        assert state.gd_cookie == ""
        assert state.filters_path == ""
        assert state.jobs_output == "output/linkedin/vagas.json"
        assert state.details_output == "output/linkedin/detalhadas.json"
        assert state.redis_url == "redis://localhost:6379/0"
        assert state.events_channel == "raxy:events"
        assert state.provider is not None and len(state.provider) > 0
        assert state.timeout == state.detail_timeout

    def test_is_dataclass(self):
        state = TuiState()
        field_names = {f.name for f in fields(state)}
        assert "portal" in field_names
        assert "keywords" in field_names
        assert "location" in field_names
        assert "valid_count" in field_names
        assert "timeout" in field_names
        assert "redis_url" in field_names

    def test_all_fields_have_defaults(self):
        for f in fields(TuiState):
            assert f.default is not None or f.default_factory is not None or f.default == ""

    def test_custom_values(self):
        state = TuiState(
            portal="gupy",
            keywords="Java",
            location="RJ",
            valid_count=10,
            timeout=30.0,
        )

        assert state.portal == "gupy"
        assert state.keywords == "Java"
        assert state.location == "RJ"
        assert state.valid_count == 10
        assert state.timeout == 30.0

    def test_redis_env_override(self, monkeypatch):
        import importlib

        monkeypatch.setenv("RAXY_REDIS_URL", "redis://custom:6379/1")
        monkeypatch.setenv("RAXY_REDIS_CHANNEL", "custom:channel")
        importlib.reload(importlib.import_module("job_search.interfaces.tui.tui_state"))
        from job_search.interfaces.tui.tui_state import TuiState as ReloadedState

        state = ReloadedState()
        assert state.redis_url == "redis://custom:6379/1"
        assert state.events_channel == "custom:channel"

    def test_provider_default_constant(self):
        from job_search.infrastructure.proxy.proxy_sources import DEFAULT_PROVIDER

        state = TuiState()
        assert state.provider == DEFAULT_PROVIDER

    def test_detail_timeout_matches_timeout(self):
        state = TuiState()
        assert state.detail_timeout == state.timeout
