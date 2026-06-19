from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.application.events.search_event import SearchEventName
from job_search.application.ports.job_board_adapter import JobBoardAdapter
from job_search.application.ports.job_search_view import JobSearchView
from job_search.domain.detailing import JobDetailingSession
from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.domain.proxy import BridgeEndpoint

PublishEvent = Callable[..., None]


class JobDetailingService:
    def __init__(self, adapter: JobBoardAdapter, view: JobSearchView, publish_event: PublishEvent) -> None:
        self.adapter = adapter
        self.view = view
        self._publish_event = publish_event

    def enrich_jobs(
        self,
        jobs: list[JobSummary],
        bridges: list[BridgeEndpoint],
        search_url: str,
        request: JobSearchRequest,
    ) -> list[JobPosting]:
        session = JobDetailingSession(
            jobs=jobs,
            bridges=bridges,
            jobs_per_proxy=request.jobs_per_proxy,
            detail_limit=request.details_limit,
        )
        jobs_to_detail = session.jobs_to_detail
        total = len(jobs_to_detail)
        results: list[JobPosting | None] = [None] * total
        done = 0

        with ThreadPoolExecutor(max_workers=request.detail_threads) as executor:
            futures = {
                executor.submit(self.detail_one_job, session, job, i, search_url, request.detail_timeout): i
                for i, job in enumerate(jobs_to_detail)
            }
            for future in as_completed(futures):
                i = futures[future]
                results[i] = future.result()
                done += 1
                self.view.info(f"[bold]Detalhes:[/] {done}/{total} - {results[i].summary.title or results[i].summary.external_id}")
                if done % 5 == 0 or done == total:
                    ok_count = sum(1 for r in results[:done] if r is not None and r.details is not None)
                    self._publish_event(SearchEventName.DETAIL_PROGRESS, f"{done}/{total}", done=done, total=total, ok=ok_count)

        enriched = [r for r in results if r is not None]
        enriched.extend(session.unprocessed_postings())
        return enriched

    def detail_one_job(
        self,
        session: JobDetailingSession,
        job: JobSummary,
        job_offset: int,
        search_url: str,
        detail_timeout: float,
    ) -> JobPosting:
        if not job.external_id:
            return session.missing_external_id(job)
        last_error = "nenhuma bridge disponivel"
        for bridge in session.bridge_candidates_for(job_offset):
            try:
                details, response = self.adapter.fetch_job_details(bridge.url, job, search_url, detail_timeout)
                return session.successful_detail(
                    job,
                    details,
                    status_code=response.status_code,
                    html_size=len(response.text),
                    bridge=bridge,
                )
            except Exception as exc:
                last_error = str(exc)
                session.mark_bridge_failed(bridge)
                logger.bind(
                    component="job_search_service",
                    portal=self.adapter.name,
                    bridge_index=bridge.index,
                    job_id=job.external_id,
                    error=last_error,
                ).warning("job_detail_bridge_failed")
                self._publish_event(
                    SearchEventName.JOB_DETAIL_BRIDGE_FAILED,
                    f"Falha ao detalhar vaga {job.external_id}",
                    level="warning",
                    bridge_index=bridge.index,
                    job_id=job.external_id,
                    error=last_error,
                )
                self.view.warn(f"Bridge {bridge.index} falhou no detalhe {job.external_id}; tentando proxima: {exc}")
        self.view.error(f"Falha ao detalhar {job.external_id}: {last_error}")
        logger.bind(
            component="job_search_service",
            portal=self.adapter.name,
            job_id=job.external_id,
            error=last_error,
        ).error("job_detail_failed")
        self._publish_event(
            SearchEventName.JOB_DETAIL_FAILED,
            f"Falha ao detalhar vaga {job.external_id}",
            level="error",
            job_id=job.external_id,
            error=last_error,
        )
        return session.failed_detail(job, last_error)
