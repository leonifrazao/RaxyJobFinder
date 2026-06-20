from __future__ import annotations

from buscador_vagas import JobFinder
from job_search.interfaces.tui.tui_state import TuiState


class TuiSearchRunner:
    def run(self, state: TuiState) -> int:
        location_id = state.location_id.strip() or None
        location_choice = int(state.location_choice.strip()) if state.location_choice.strip() else None

        finder = JobFinder(
            portal=state.portal,
            keywords=state.keywords,
            location=state.location,
            location_id=location_id,
            location_choice=location_choice,
            work_type=state.work_type.strip() or None,
            under_10_applicants=state.under_10_applicants,
            proxy_provider=state.provider,
            valid_count=state.valid_count,
            jobs_per_proxy=state.jobs_per_proxy,
            max_count=state.max_count,
            threads=state.threads,
            timeout=state.timeout,
            detail_timeout=state.detail_timeout,
            details_limit=state.details_limit,
            max_jobs=state.max_jobs,
            start=state.start,
            detail_threads=state.detail_threads,
            gd_cookie=state.gd_cookie,
            filters_path=state.filters_path.strip() or None,
            silent=True,
        )
        finder.search(
            jobs_output=state.jobs_output,
            details_output=state.details_output,
        )
        return 0
