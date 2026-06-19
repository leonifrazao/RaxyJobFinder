from __future__ import annotations

from job_search.interfaces.tui.tui_argument_builder import TuiArgumentBuilder
from job_search.interfaces.tui.tui_state import TuiState


class TestTuiArgumentBuilder:
    def test_builds_cli_arguments(self):
        args = TuiArgumentBuilder().build(
            TuiState(
                portal="linkedin",
                keywords="Python",
                location="Brasil",
                provider="united-states",
                valid_count=1,
                max_count=10,
                threads=3,
                timeout=15.0,
                detail_timeout=8.0,
                max_jobs=3,
                details_limit=1,
                show_jobs=3,
                jobs_output="jobs.json",
                details_output="details.json",
            )
        )

        assert args == [
            "--portal", "linkedin",
            "--keywords", "Python",
            "--location", "Brasil",
            "--location-choice", "1",
            "--provider", "united-states",
            "--valid-count", "1",
            "--max-count", "10",
            "--threads", "3",
            "--timeout", "15.0",
            "--detail-timeout", "8.0",
            "--jobs-per-proxy", "1",
            "--max-jobs", "3",
            "--details-limit", "1",
            "--show-jobs", "3",
            "--jobs-output", "jobs.json",
            "--details-output", "details.json",
        ]
