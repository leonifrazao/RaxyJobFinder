from __future__ import annotations

from dataclasses import fields

from job_search.infrastructure.config import load_settings
from job_search.interfaces.tui.tui_state import TuiState


class TestTuiState:
    def test_default_values(self):
        state = TuiState()

        assert state.portal == "linkedin"
        assert state.keywords == "Vagas"
        assert state.location == "Brasil"
        assert state.location_id == ""
        assert state.location_choice == "1"
        assert state.work_type == "normal"
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

    def test_from_config_matches_yaml(self):
        cfg = load_settings().defaults
        state = TuiState.from_config()

        assert state.portal == cfg.portal
        assert state.keywords == cfg.keywords
        assert state.location == cfg.location
        assert state.work_type == cfg.work_type
        assert state.valid_count == cfg.valid_count
        assert state.jobs_per_proxy == cfg.jobs_per_proxy
        assert state.max_count == cfg.max_count
        assert state.threads == cfg.threads
        assert state.timeout == cfg.timeout
        assert state.detail_timeout == cfg.detail_timeout
        assert state.details_limit == cfg.details_limit
        assert state.start == cfg.start
        assert state.max_jobs == cfg.max_jobs
        assert state.detail_threads == cfg.detail_threads
        assert state.show_jobs == cfg.show_jobs
        assert state.gd_cookie == cfg.gd_cookie
        assert state.filters_path == cfg.filters_path

    def test_from_config_sets_provider(self):
        state = TuiState.from_config()
        assert state.provider == load_settings().proxy.default_provider

    def test_from_config_sets_output_paths(self):
        state = TuiState.from_config()
        portal = load_settings().defaults.portal
        assert state.jobs_output == f"output/{portal}/vagas.json"
        assert state.details_output == f"output/{portal}/detalhadas.json"

    def test_from_config_sets_redis(self):
        state = TuiState.from_config()
        assert state.redis_url == load_settings().redis.url
        assert state.events_channel == load_settings().redis.channel

    def test_is_dataclass(self):
        state = TuiState()
        field_names = {f.name for f in fields(state)}
        assert "portal" in field_names
        assert "keywords" in field_names
        assert "location" in field_names
        assert "work_type" in field_names
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

    def test_detail_timeout_matches_timeout(self):
        state = TuiState()
        assert state.detail_timeout == state.timeout
