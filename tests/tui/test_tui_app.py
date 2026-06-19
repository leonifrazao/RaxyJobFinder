from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytermgui as ptg
import pytest

from job_search.interfaces.tui.tui_app import TuiApp, _float, _int, _section, _text
from job_search.interfaces.tui.tui_state import TuiState


class FakeField:
    def __init__(self, value: str) -> None:
        self.value = value


class SettableField:
    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str) -> None:
        self._value = v


class TestHelpers:
    def test_text_strips_value(self):
        field = FakeField("  linkedin  ")
        assert _text(field) == "linkedin"

    def test_text_empty(self):
        field = FakeField("")
        assert _text(field) == ""

    def test_text_not_string(self):
        field = FakeField("123")
        assert _text(field) == "123"

    def test_int_parses_valid(self):
        field = FakeField("42")
        assert _int(field) == 42

    def test_int_empty_returns_zero(self):
        field = FakeField("")
        assert _int(field) == 0

    def test_int_strips_whitespace(self):
        field = FakeField("  99  ")
        assert _int(field) == 99

    def test_float_parses_valid(self):
        field = FakeField("15.5")
        assert _float(field) == 15.5

    def test_float_empty_returns_zero(self):
        field = FakeField("")
        assert _float(field) == 0.0

    def test_float_strips_whitespace(self):
        field = FakeField("  7.5  ")
        assert _float(field) == 7.5

    def test_section_returns_label(self):
        label = _section("PROXY")
        assert isinstance(label, ptg.Label)


class TestTuiApp:
    def test_initial_state(self):
        app = TuiApp()
        assert app._search_started is False
        assert app._manager is None
        assert app._fields == {}
        assert app._proxy_label is None
        assert app._search_label is None
        assert app._detail_label is None
        assert app._save_label is None
        assert app._runner is not None
        assert app._reader is not None

    def test_build_fields_creates_all_inputs(self):
        app = TuiApp()
        state = TuiState(portal="gupy", keywords="Java", location="RJ")
        fields = app._build_fields(state)

        assert fields["portal"].value == "gupy"
        assert fields["keywords"].value == "Java"
        assert fields["location"].value == "RJ"
        assert fields["valid_count"].value == "25"
        assert fields["timeout"].value == "15.0"
        assert fields["redis_url"].value is not None
        assert fields["events_channel"].value is not None
        assert len(fields) == 23

    def test_build_fields_includes_all_keys(self):
        app = TuiApp()
        keys = app._build_fields(TuiState()).keys()
        expected = {
            "portal", "keywords", "location", "location_id", "location_choice",
            "provider", "valid_count", "jobs_per_proxy", "max_count", "threads",
            "timeout", "detail_timeout", "max_jobs", "start", "details_limit",
            "detail_threads", "show_jobs", "gd_cookie", "filters_path",
            "jobs_output", "details_output", "redis_url", "events_channel",
        }
        assert keys == expected

    def test_build_fields_prompt_overwrites_defaults(self):
        app = TuiApp()
        fields = app._build_fields(TuiState(portal="glassdoor"))
        assert fields["portal"].value == "glassdoor"

    def test_set_proxy_updates_label(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._set_proxy("[green]OK[/]")
        assert app._proxy_label.value == "proxy:    [green]OK[/]"

    def test_set_proxy_skips_when_none(self):
        app = TuiApp()
        app._proxy_label = None
        app._set_proxy("x")

    def test_set_search_updates_label(self):
        app = TuiApp()
        app._search_label = MagicMock()
        app._set_search("[red]falha[/]")
        assert app._search_label.value == "busca:    [red]falha[/]"

    def test_set_detail_updates_label(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._set_detail("[yellow]processando...[/]")
        assert app._detail_label.value == "detalhes: [yellow]processando...[/]"

    def test_set_save_updates_label(self):
        app = TuiApp()
        app._save_label = MagicMock()
        app._set_save("[green]salvo[/]")
        assert app._save_label.value == "salvar:   [green]salvo[/]"

    def test_set_methods_update_independently(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._search_label = MagicMock()
        app._detail_label = MagicMock()
        app._save_label = MagicMock()
        app._set_proxy("p")
        app._set_search("s")
        app._set_detail("d")
        app._set_save("v")
        assert app._proxy_label.value == "proxy:    p"
        assert app._search_label.value == "busca:    s"
        assert app._detail_label.value == "detalhes: d"
        assert app._save_label.value == "salvar:   v"

    def test_handle_event_proxy_prepare_started(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_prepare_started"})
        assert app._proxy_label.value == "proxy:    [yellow]baixando proxies...[/]"

    def test_handle_event_proxy_testing(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_testing"})
        assert app._proxy_label.value == "proxy:    [yellow]testando proxies...[/]"

    def test_handle_event_proxy_tested(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_tested", "payload": {"working": 5, "total": 10}})
        assert app._proxy_label.value == "proxy:    [green]5/10 OK[/], [yellow]iniciando bridges...[/]"

    def test_handle_event_proxy_tested_zero_defaults(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_tested"})
        assert app._proxy_label.value == "proxy:    [green]0/0 OK[/], [yellow]iniciando bridges...[/]"

    def test_handle_event_proxy_verifying(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_verifying"})
        assert app._proxy_label.value == "proxy:    [yellow]verificando bridges...[/]"

    def test_handle_event_proxy_bridge_verified(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_bridge_verified", "payload": {"index": 3, "total": 5}})
        assert app._proxy_label.value == "proxy:    [green]bridge 3/5 OK[/]"

    def test_handle_event_proxy_bridge_failed(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_bridge_failed", "payload": {"index": 2, "total": 5}})
        assert app._proxy_label.value == "proxy:    [red]bridge 2/5 falhou[/]"

    def test_handle_event_proxy_no_working(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_no_working"})
        assert app._proxy_label.value == "proxy:    [red]nenhuma proxy funcional![/]"

    def test_handle_event_proxy_prepare_finished(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._handle_event({"name": "proxy_prepare_finished", "payload": {"bridges": 8}})
        assert app._proxy_label.value == "proxy:    [green]8 bridges ativas[/]"

    def test_handle_event_search_bridge_attempt(self):
        app = TuiApp()
        app._search_label = MagicMock()
        app._handle_event({"name": "search_bridge_attempt"})
        assert app._search_label.value == "busca:    [yellow]buscando vagas...[/]"

    def test_handle_event_search_bridge_succeeded(self):
        app = TuiApp()
        app._search_label = MagicMock()
        app._handle_event({"name": "search_bridge_succeeded", "payload": {"jobs_count": 42, "status_code": 200}})
        assert app._search_label.value == "busca:    [green]42 vagas encontradas[/] (HTTP 200)"

    def test_handle_event_search_bridge_succeeded_defaults(self):
        app = TuiApp()
        app._search_label = MagicMock()
        app._handle_event({"name": "search_bridge_succeeded"})
        assert app._search_label.value == "busca:    [green]0 vagas encontradas[/] (HTTP 0)"

    def test_handle_event_search_bridge_failed(self):
        app = TuiApp()
        app._search_label = MagicMock()
        app._handle_event({"name": "search_bridge_failed"})
        assert app._search_label.value == "busca:    [red]falha na busca[/]"

    def test_handle_event_detail_started(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "detail_started", "payload": {"total": 20}})
        assert app._detail_label.value == "detalhes: [yellow]detalhando 0/20...[/]"
        assert app._detail_total == 20

    def test_handle_event_detail_started_default_total(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "detail_started"})
        assert app._detail_label.value == "detalhes: [yellow]detalhando 0/0...[/]"
        assert app._detail_total == 0

    def test_handle_event_detail_progress(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "detail_progress", "payload": {"done": 10, "total": 20, "ok": 8}})
        assert app._detail_label.value == "detalhes: [yellow]10/20[/] ([green]8 OK[/])"

    def test_handle_event_detail_progress_defaults(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "detail_progress"})
        assert app._detail_label.value == "detalhes: [yellow]0/0[/] ([green]0 OK[/])"

    def test_handle_event_detail_failed(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "detail_failed", "message": "timeout"})
        assert app._detail_label.value == "detalhes: [red]timeout[/]"

    def test_handle_event_detail_failed_empty_message(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "detail_failed"})
        assert app._detail_label.value == "detalhes: [red][/]"

    def test_handle_event_save_started(self):
        app = TuiApp()
        app._save_label = MagicMock()
        app._handle_event({"name": "save_started"})
        assert app._save_label.value == "salvar:   [yellow]salvando vagas...[/]"

    def test_handle_event_save_details_started(self):
        app = TuiApp()
        app._save_label = MagicMock()
        app._handle_event({"name": "save_details_started"})
        assert app._save_label.value == "salvar:   [yellow]salvando detalhes...[/]"

    def test_handle_event_save_finished(self):
        app = TuiApp()
        app._save_label = MagicMock()
        app._handle_event({"name": "save_finished"})
        assert app._save_label.value == "salvar:   [green]resultados salvos[/]"

    def test_handle_event_job_search_finished(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "job_search_finished", "payload": {"jobs_detailed": 15}})
        assert app._detail_label.value == "detalhes: [green]15 vagas detalhadas[/]"

    def test_handle_event_job_search_finished_defaults(self):
        app = TuiApp()
        app._detail_label = MagicMock()
        app._handle_event({"name": "job_search_finished"})
        assert app._detail_label.value == "detalhes: [green]0 vagas detalhadas[/]"

    def test_handle_event_unknown_does_nothing(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._search_label = MagicMock()
        app._detail_label = MagicMock()
        app._save_label = MagicMock()
        original = app._proxy_label.value
        app._handle_event({"name": "unknown_event"})
        assert app._proxy_label.value is original

    def test_handle_event_empty_name_does_nothing(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        original = app._proxy_label.value
        app._handle_event({})
        assert app._proxy_label.value is original

    def test_reset_status_resets_all_labels(self):
        app = TuiApp()
        app._proxy_label = MagicMock()
        app._search_label = MagicMock()
        app._detail_label = MagicMock()
        app._save_label = MagicMock()
        app._reset_status()
        assert app._proxy_label.value == "proxy:    [dim]aguardando...[/]"
        assert app._search_label.value == "busca:    [dim]aguardando...[/]"
        assert app._detail_label.value == "detalhes: [dim]aguardando...[/]"
        assert app._save_label.value == "salvar:   [dim]aguardando...[/]"

    def test_reset_fields_restores_defaults(self):
        app = TuiApp()
        app._fields = app._build_fields(TuiState(portal="gupy", keywords="Java"))
        keys = list(app._fields.keys())
        for k in keys:
            app._fields[k] = SettableField(app._fields[k].value)
        app._reset_fields()
        defaults = TuiState.from_config()
        assert app._fields["portal"].value == defaults.portal
        assert app._fields["keywords"].value == defaults.keywords
        assert app._fields["valid_count"].value == str(defaults.valid_count)
        assert app._fields["timeout"].value == str(defaults.timeout)

    def test_reset_fields_skips_missing_keys(self):
        app = TuiApp()
        app._fields = {"portal": SettableField("gupy")}
        app._reset_fields()
        assert app._fields["portal"].value == "linkedin"

    def test_submit_ignored_when_search_started(self):
        app = TuiApp()
        app._search_started = True
        app._reader = MagicMock()
        app._submit()
        app._reader.read.assert_not_called()

    def test_submit_shows_error_on_invalid_input(self):
        app = TuiApp()
        app._show_error = MagicMock()
        app._fields = app._build_fields(TuiState())
        app._fields["valid_count"] = FakeField("not_a_number")
        app._submit()
        app._show_error.assert_called_once()

    def test_submit_sets_env_and_starts(self, monkeypatch):
        threads = []

        class FakeThread:
            def __init__(self, target=None, args=None, daemon=False) -> None:
                self._target = target
                self._args = args
                self.daemon = daemon

            def start(self) -> None:
                threads.append(self)

        monkeypatch.setattr("job_search.interfaces.tui.tui_app.threading.Thread", FakeThread)
        app = TuiApp()
        app._fields = app._build_fields(TuiState(portal="gupy"))
        app._submit()
        assert app._search_started is True
        assert os.environ.get("RAXY_REDIS_URL") is not None

    def test_show_error_does_nothing_without_manager(self):
        app = TuiApp()
        app._manager = None
        app._show_error("error")

    def test_show_help_does_nothing_without_manager(self):
        app = TuiApp()
        app._manager = None
        app._show_help()

    def test_run_returns_zero(self):
        app = TuiApp()
        app._run_window = MagicMock()
        result = app.run()
        assert result == 0
        app._run_window.assert_called_once()

    def test_start_search_runs_and_resets_flag(self, monkeypatch):
        threads_started = []

        class TrackingThread:
            def __init__(self, target, daemon=False) -> None:
                self._target = target

            def start(self) -> None:
                threads_started.append(self)
                self._target()

        monkeypatch.setattr("job_search.interfaces.tui.tui_app.threading.Thread", TrackingThread)
        app = TuiApp()
        app._runner = MagicMock()
        app._runner.run.return_value = 0
        state = TuiState()
        app._start_search(state)
        app._runner.run.assert_called_once_with(state)
        assert app._search_started is False

    def test_start_search_sets_labels_on_failure(self, monkeypatch):
        class ImmediateThread:
            def __init__(self, target, daemon=False) -> None:
                self._target = target

            def start(self) -> None:
                self._target()

        monkeypatch.setattr("job_search.interfaces.tui.tui_app.threading.Thread", ImmediateThread)
        app = TuiApp()
        app._runner = MagicMock()
        app._runner.run.side_effect = RuntimeError("boom")
        app._proxy_label = MagicMock()
        app._search_label = MagicMock()
        app._detail_label = MagicMock()
        app._save_label = MagicMock()
        app._start_search(TuiState())
        assert app._proxy_label.value == "proxy:    [red]falha[/]"
        assert app._search_label.value == "busca:    [red]falha[/]"
        assert app._detail_label.value == "detalhes: [red]falha[/]"
        assert app._save_label.value == "salvar:   [red]falha[/]"
