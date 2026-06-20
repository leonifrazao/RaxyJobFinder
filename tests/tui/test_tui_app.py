from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from job_search.infrastructure.config import reset_settings
from job_search.interfaces.tui.tui_app import TuiApp, _default_first
from job_search.interfaces.tui.tui_state import TuiState


class FakePrompter:
    def __init__(self, *, selects=None, texts=None, confirms=None) -> None:
        self.selects = list(selects or [])
        self.texts = list(texts or [])
        self.confirms = list(confirms or [])
        self.messages: list[tuple[str, str]] = []
        self.select_calls = []
        self.text_calls = []
        self.confirm_calls = []

    def select(self, title, text, values, default):
        self.select_calls.append((title, text, list(values), default))
        return self.selects.pop(0)

    def text(self, title, text, default=""):
        self.text_calls.append((title, text, default))
        if self.texts:
            return self.texts.pop(0)
        return default

    def confirm(self, title, text, default=False):
        self.confirm_calls.append((title, text, default))
        if self.confirms:
            return self.confirms.pop(0)
        return default

    def message(self, title, text):
        self.messages.append((title, text))


class FakeSubscriber:
    def __init__(self) -> None:
        self.listen_calls = []

    def listen(self, stop_event, handler):
        self.listen_calls.append((stop_event, handler))


@pytest.fixture(autouse=True)
def reset_config_cache():
    reset_settings()
    yield
    reset_settings()


def write_config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("defaults:\n  portal: linkedin\n", encoding="utf-8")
    return path


class TestHelpers:
    def test_default_first_moves_default_to_front(self):
        values = [("gupy", "Gupy"), ("linkedin", "LinkedIn")]

        result = _default_first(values, "linkedin")

        assert result == [("linkedin", "LinkedIn"), ("gupy", "Gupy")]

class TestTuiAppPromptState:
    def test_prompt_state_uses_selectors_for_portal_and_work_type(self):
        prompter = FakePrompter(selects=["linkedin", "remote"], confirms=[True])
        app = TuiApp(prompter=prompter)

        state = app._prompt_state(TuiState(provider="united-states"))

        assert state is not None
        assert state.portal == "linkedin"
        assert state.provider == "united-states"
        assert state.work_type == "remote"
        assert state.under_10_applicants is True
        portal_values = prompter.select_calls[0][2]
        assert [value for value, _ in portal_values] == ["linkedin", "gupy", "glassdoor"]
        assert len(prompter.select_calls) == 2

    def test_prompt_state_skips_linkedin_only_options_for_gupy(self):
        prompter = FakePrompter(selects=["gupy"])
        app = TuiApp(prompter=prompter)

        state = app._prompt_state(TuiState())

        assert state is not None
        assert state.portal == "gupy"
        assert state.work_type == "normal"
        assert state.under_10_applicants is False
        assert len(prompter.select_calls) == 1
        assert prompter.confirm_calls == []

    def test_prompt_state_asks_glassdoor_cookie_only_for_glassdoor(self):
        texts = ["Python", "Brasil", "", "1", "cookie=value", ""]
        prompter = FakePrompter(selects=["glassdoor"], texts=texts)
        app = TuiApp(prompter=prompter)

        state = app._prompt_state(TuiState())

        assert state is not None
        assert state.portal == "glassdoor"
        assert state.gd_cookie == "cookie=value"

    def test_prompt_state_cancel_returns_none(self):
        prompter = FakePrompter(selects=[None])
        app = TuiApp(prompter=prompter)

        assert app._prompt_state(TuiState()) is None

    def test_prompt_state_text_cancel_shows_message_and_returns_none(self):
        prompter = FakePrompter(selects=["gupy"], texts=[None])
        app = TuiApp(prompter=prompter)

        assert app._prompt_state(TuiState()) is None
        assert prompter.messages[-1][0] == "Valor invalido"


class TestTuiAppRun:
    def test_run_executes_runner_and_sets_env(self, tmp_path):
        runner = MagicMock()
        runner.run.return_value = 0
        prompter = FakePrompter(selects=["gupy"])
        app = TuiApp(runner=runner, prompter=prompter, config_path=write_config(tmp_path))
        app._start_event_listener = MagicMock()
        app._stop_event_listener = MagicMock()

        result = app.run()

        assert result == 0
        runner.run.assert_called_once()
        state = runner.run.call_args.args[0]
        assert state.portal == "gupy"
        assert os.environ["RAXY_REDIS_URL"] == state.redis_url
        assert os.environ["RAXY_REDIS_CHANNEL"] == state.events_channel
        assert prompter.messages[-1][0] == "Busca finalizada"
        app._stop_event_listener.assert_called_once()

    def test_run_returns_zero_when_cancelled(self, tmp_path):
        runner = MagicMock()
        prompter = FakePrompter(selects=[None])
        app = TuiApp(runner=runner, prompter=prompter, config_path=write_config(tmp_path))

        assert app.run() == 0
        runner.run.assert_not_called()

    def test_run_reports_backend_error(self, tmp_path):
        runner = MagicMock()
        runner.run.side_effect = RuntimeError("boom")
        prompter = FakePrompter(selects=["gupy"])
        app = TuiApp(runner=runner, prompter=prompter, config_path=write_config(tmp_path))
        app._start_event_listener = MagicMock()
        app._stop_event_listener = MagicMock()

        assert app.run() == 1
        assert prompter.messages[-1] == ("Erro na busca", "boom")

    def test_run_requires_config_file(self, tmp_path):
        runner = MagicMock()
        prompter = FakePrompter()
        app = TuiApp(runner=runner, prompter=prompter, config_path=tmp_path / "missing.yaml")

        assert app.run() == 1
        runner.run.assert_not_called()
        assert prompter.messages[-1][0] == "Config obrigatorio"


class TestTuiAppEvents:
    def test_start_event_listener_uses_factory_and_stores_lifecycle(self, monkeypatch):
        subscriber = FakeSubscriber()
        started = []

        class FakeThread:
            def __init__(self, target, args, daemon=False) -> None:
                self.target = target
                self.args = args
                self.daemon = daemon

            def start(self):
                started.append(self)

            def join(self, timeout=None):
                pass

        monkeypatch.setattr("job_search.interfaces.tui.tui_app.threading.Thread", FakeThread)
        app = TuiApp(subscriber_factory=lambda redis_url, channel: subscriber)

        app._start_event_listener(TuiState(redis_url="redis://test", events_channel="events"))

        assert app._event_stop_event is not None
        assert app._event_thread is started[0]
        assert started[0].args[1] == app._handle_event

    def test_stop_event_listener_sets_event_and_joins_thread(self):
        app = TuiApp()
        stop_event = MagicMock()
        thread = MagicMock()
        app._event_stop_event = stop_event
        app._event_thread = thread

        app._stop_event_listener()

        stop_event.set.assert_called_once()
        thread.join.assert_called_once_with(timeout=1.0)
        assert app._event_stop_event is None
        assert app._event_thread is None

    def test_handle_event_formats_and_prints(self):
        printed = []
        app = TuiApp(event_printer=printed.append)

        app._handle_event({"name": "search_bridge_succeeded", "payload": {"jobs_count": 2}})

        assert len(app._event_lines) == 1
        assert printed == app._event_lines
        assert "2 vagas" in printed[0]
