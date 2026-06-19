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
        assert "[INFO] linkedin Busca iniciada" in text
        assert text.startswith("[")

    def test_falls_back_to_event_name(self):
        text = TuiEventFormatter().format({"name": "bridges_prepared"})
        assert "[INFO] bridges_prepared" in text
        assert text.startswith("[")

    def test_includes_timestamp(self):
        text = TuiEventFormatter().format({"name": "test"})
        parts = text.split()
        assert len(parts) >= 3
        assert parts[0].startswith("[") and parts[0].endswith("]")

    def test_includes_bridges(self):
        text = TuiEventFormatter().format({
            "name": "proxy_prepare_finished",
            "payload": {"bridges_count": 8},
        })
        assert "8 bridges" in text

    def test_includes_working_total(self):
        text = TuiEventFormatter().format({
            "name": "proxy_tested",
            "payload": {"working": 5, "total": 10},
        })
        assert "5/10 OK" in text

    def test_includes_jobs_count(self):
        text = TuiEventFormatter().format({
            "name": "search_finished",
            "payload": {"jobs_count": 42},
        })
        assert "42 vagas" in text

    def test_includes_status_code(self):
        text = TuiEventFormatter().format({
            "name": "search_bridge_succeeded",
            "payload": {"status_code": 200},
        })
        assert "HTTP 200" in text

    def test_includes_index(self):
        text = TuiEventFormatter().format({
            "name": "bridge_event",
            "payload": {"index": 3},
        })
        assert "#3" in text

    def test_includes_error(self):
        text = TuiEventFormatter().format({
            "name": "bridge_failed",
            "payload": {"error": "connection refused"},
        })
        assert "connection refused" in text

    def test_no_payload_still_works(self):
        text = TuiEventFormatter().format({"name": "simple"})
        assert "[INFO] simple" in text

    def test_includes_expected_bridges(self):
        text = TuiEventFormatter().format({
            "name": "bridges_preparing",
            "payload": {"expected": 10},
        })
        assert "10 bridges esperadas" in text
