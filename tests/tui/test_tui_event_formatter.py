from __future__ import annotations

from job_search.interfaces.tui.tui_event_formatter import TuiEventFormatter


class TestTuiEventFormatter:
    def test_formats_event_with_portal(self):
        text = TuiEventFormatter().format(
            {
                "level": "info",
                "message": "Busca iniciada",
                "payload": {"portal": "linkedin"},
            }
        )

        assert text == "[INFO] linkedin Busca iniciada"

    def test_falls_back_to_event_name(self):
        text = TuiEventFormatter().format({"name": "bridges_prepared"})

        assert text == "[INFO] bridges_prepared"
