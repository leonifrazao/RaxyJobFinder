from __future__ import annotations

from buscador_vagas import JobFinder
from job_search.interfaces.tui.tui_state import TuiState


class TuiSearchRunner:
    def run(self, state: TuiState) -> int:
        finder = JobFinder(
            portal=state.portal,
            keywords=state.keywords,
            location=state.location,
            location_choice=1,
            proxy_provider=state.provider,
            valid_count=state.valid_count,
            jobs_per_proxy=1,
            max_count=state.max_count,
            threads=state.threads,
            timeout=state.timeout,
            detail_timeout=state.detail_timeout,
            details_limit=state.details_limit,
            max_jobs=state.max_jobs,
            detail_threads=state.detail_threads,
            silent=True,
        )
        finder.search(
            jobs_output=state.jobs_output,
            details_output=state.details_output,
        )
        return 0
