from __future__ import annotations

from job_search.interfaces.tui.tui_state import TuiState


class TuiArgumentBuilder:
    def build(self, state: TuiState) -> list[str]:
        return [
            "--portal", state.portal,
            "--keywords", state.keywords,
            "--location", state.location,
            "--location-choice", "1",
            "--provider", state.provider,
            "--valid-count", str(state.valid_count),
            "--max-count", str(state.max_count),
            "--threads", str(state.threads),
            "--timeout", str(state.timeout),
            "--detail-timeout", str(state.detail_timeout),
            "--jobs-per-proxy", "1",
            "--max-jobs", str(state.max_jobs),
            "--details-limit", str(state.details_limit),
            "--show-jobs", str(state.show_jobs),
            "--jobs-output", state.jobs_output,
            "--details-output", state.details_output,
        ]
