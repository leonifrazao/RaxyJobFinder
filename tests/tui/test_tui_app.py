from __future__ import annotations

from unittest.mock import MagicMock

from job_search.interfaces.tui.tui_app import TuiApp
from job_search.interfaces.tui.tui_state import TuiState


class TestTuiApp:
    def test_backend_failure_adds_error_log_path_event(self, monkeypatch):
        class ImmediateThread:
            def __init__(self, target, daemon=False) -> None:
                self._target = target

            def start(self) -> None:
                self._target()

        app = TuiApp()
        app._runner = MagicMock()
        app._runner.run.side_effect = RuntimeError("boom")
        monkeypatch.setenv("RAXY_ERROR_LOG_PATH", "logs/test-error.log")
        monkeypatch.setattr("job_search.interfaces.tui.tui_app.threading.Thread", ImmediateThread)

        app._start_search(MagicMock(), TuiState())

        assert app._events[-2] == "[ERROR] Backend falhou: boom"
        assert app._events[-1] == "[ERROR] Log salvo em logs/test-error.log"
