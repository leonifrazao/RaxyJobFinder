from __future__ import annotations

from unittest.mock import patch

from job_search.interfaces.tui.tui_search_runner import TuiSearchRunner
from job_search.interfaces.tui.tui_state import TuiState


class TestTuiSearchRunner:
    def test_runs_sdk_backend(self):
        with patch("job_search.interfaces.tui.tui_search_runner.JobFinder") as job_finder:
            finder = job_finder.return_value
            finder.search.return_value = []

            result = TuiSearchRunner().run(TuiState(jobs_output="jobs.json", details_output="details.json"))

        assert result == 0
        job_finder.assert_called_once()
        finder.search.assert_called_once_with(jobs_output="jobs.json", details_output="details.json")
