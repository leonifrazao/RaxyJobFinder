from __future__ import annotations

from typing import Any

from loguru import logger

from job_search.application.bridge_search_service import BridgeSearchService
from job_search.application.job_detailing_service import JobDetailingService
from job_search.application.search_result_saver import SearchResultSaver
from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.application.dto.output.search_result import SearchResult
from job_search.application.events.noop_search_event_publisher import NoopSearchEventPublisher
from job_search.application.events.search_event import SearchEvent, SearchEventName
from job_search.application.ports.job_board_adapter import JobBoardAdapter
from job_search.application.ports.job_filter_repository import JobFilterRepository
from job_search.application.ports.job_repository import JobRepository
from job_search.application.ports.job_search_view import JobSearchView
from job_search.application.ports.proxy_pool import ProxyPool
from job_search.application.ports.search_event_publisher import SearchEventPublisher
from job_search.domain.detailing import JobDetailingSession
from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.domain.proxy import BridgeEndpoint
from job_search.domain.search_query import SearchQuery


class JobSearchService:
    def __init__(
        self,
        adapter: JobBoardAdapter,
        proxy_pool: ProxyPool,
        repository: JobRepository,
        filter_repository: JobFilterRepository,
        view: JobSearchView,
        event_publisher: SearchEventPublisher | None = None,
    ) -> None:
        self.adapter = adapter
        self.proxy_pool = proxy_pool
        self.repository = repository
        self.filter_repository = filter_repository
        self.view = view
        self.event_publisher = event_publisher or NoopSearchEventPublisher()
        self.bridge_search = BridgeSearchService(adapter, view, self._publish_event)
        self.job_detailing = JobDetailingService(adapter, view, self._publish_event)
        self.result_saver = SearchResultSaver(repository, view, self._publish_event)

    def run(self, request: JobSearchRequest) -> int:
        log = logger.bind(
            component="job_search_service",
            portal=self.adapter.name,
            keywords=request.keywords,
            location=request.location,
            provider_proxy_sources=len(request.proxy_sources),
        )
        log.info("job_search_started")
        self._publish_event(
            SearchEventName.JOB_SEARCH_STARTED,
            f"Busca iniciada em {self.adapter.name}",
            keywords=request.keywords,
            location=request.location,
            proxy_sources_count=len(request.proxy_sources),
        )
        query = SearchQuery(request.keywords, request.location, request.location_id)
        bridges = self._prepare_bridges(query, request)
        try:
            query = self._resolve_location(query, bridges, request)
            result = self._search_with_first_working_bridge(query, bridges, request.timeout, request.max_jobs, request.start)
            if result is None:
                return self._finish_without_working_bridge(log)

            if not result.jobs:
                return self._finish_without_jobs(request, result, log)

            self.view.show_jobs(result.jobs, request.show_jobs)
            self._publish_event(SearchEventName.DETAIL_STARTED, f"Iniciando detalhamento de {len(result.jobs)} vagas...", total=len(result.jobs))
            detailed_jobs = self._enrich_jobs(result.jobs, bridges, result.search_url, request)
            filtered_jobs = self._filter_jobs(detailed_jobs, request.filters_path)

            self._save_results(request, filtered_jobs)
            self.view.show_job_details(filtered_jobs, request.show_jobs)
            self._publish_finished_events(request, result, detailed_jobs, filtered_jobs, log)
            return 0
        finally:
            self.proxy_pool.stop()

    def _finish_without_working_bridge(self, log: Any) -> int:
        log.warning("job_search_no_working_bridge")
        self._publish_event(SearchEventName.JOB_SEARCH_NO_WORKING_BRIDGE, "Nenhuma bridge retornou resposta", level="warning")
        self.view.error("Nenhuma bridge conseguiu retornar resposta do portal.")
        return 1

    def _finish_without_jobs(self, request: JobSearchRequest, result: SearchResult, log: Any) -> int:
        log.bind(search_url=result.search_url).warning("job_search_no_jobs")
        self._publish_event(SearchEventName.JOB_SEARCH_NO_JOBS, "Nenhuma vaga encontrada", level="warning", search_url=result.search_url)
        self.view.warn("Nenhuma vaga encontrada.")
        self.result_saver.save_empty_outputs(request)
        return 0

    def _save_results(self, request: JobSearchRequest, filtered_jobs: list[JobPosting]) -> None:
        self.result_saver.save_results(request, filtered_jobs)

    def _publish_finished_events(
        self,
        request: JobSearchRequest,
        result: SearchResult,
        detailed_jobs: list[JobPosting],
        filtered_jobs: list[JobPosting],
        log: Any,
    ) -> None:
        log.bind(
            jobs_found=len(result.jobs),
            jobs_detailed=len(detailed_jobs),
            jobs_filtered=len(filtered_jobs),
            jobs_output=request.jobs_output,
            details_output=request.details_output,
        ).info("job_search_finished")
        self._publish_event(
            SearchEventName.JOB_SEARCH_FINISHED,
            f"Busca finalizada com {len(filtered_jobs)} vagas",
            jobs_found=len(result.jobs),
            jobs_detailed=len(detailed_jobs),
            jobs_filtered=len(filtered_jobs),
            jobs_output=request.jobs_output,
            details_output=request.details_output,
        )
        self._publish_event(
            SearchEventName.SEARCH_DATA,
            f"Dados completos de {len(filtered_jobs)} vagas",
            portal=self.adapter.name,
            jobs_output=request.jobs_output,
            details_output=request.details_output,
            jobs_count=len(filtered_jobs),
            data=[job.to_dict() for job in filtered_jobs],
        )

    def _prepare_bridges(self, query: SearchQuery, request: JobSearchRequest) -> list[BridgeEndpoint]:
        test_url = self.adapter.build_search_url(query)
        self._publish_event(SearchEventName.PROXY_PREPARE_STARTED, "Iniciando preparacao de proxies...")

        def on_progress(name: str, message: str, payload: dict) -> None:
            self._publish_event(name, message, **payload)

        bridges = self.proxy_pool.prepare(
            sources=request.proxy_sources,
            max_count=request.max_count,
            valid_count=request.valid_count,
            threads=request.threads,
            timeout=request.timeout,
            test_url=test_url,
            progress_callback=on_progress,
        )
        self.view.info(f"[bold]Bridges ativas:[/] {len(bridges)}")
        self.view.info(f"[bold]Rotacao de detalhes:[/] 1 proxy a cada {max(1, request.jobs_per_proxy)} vagas")
        logger.bind(
            component="job_search_service",
            portal=self.adapter.name,
            bridges_count=len(bridges),
        ).info("bridges_prepared")
        self._publish_event(SearchEventName.BRIDGES_PREPARED, f"{len(bridges)} bridges ativas", bridges_count=len(bridges))
        return bridges

    def _resolve_location(self, query: SearchQuery, bridges: list[BridgeEndpoint], request: JobSearchRequest) -> SearchQuery:
        return self.bridge_search.resolve_location(query, bridges, request)

    def _search_with_first_working_bridge(self, query: SearchQuery, bridges: list[BridgeEndpoint], timeout: float, max_jobs: int = 0, start: int = 0):
        return self.bridge_search.search_with_first_working_bridge(query, bridges, timeout, max_jobs=max_jobs, start=start)

    def _enrich_jobs(self, jobs: list[JobSummary], bridges: list[BridgeEndpoint], search_url: str, request: JobSearchRequest) -> list[JobPosting]:
        return self.job_detailing.enrich_jobs(jobs, bridges, search_url, request)

    def _detail_one_job(
        self,
        session: JobDetailingSession,
        job: JobSummary,
        job_offset: int,
        search_url: str,
        detail_timeout: float,
    ) -> JobPosting:
        return self.job_detailing.detail_one_job(session, job, job_offset, search_url, detail_timeout)

    def _filter_jobs(self, jobs: list[JobPosting], filters_path: str | None) -> list[JobPosting]:
        filters = self.filter_repository.load(filters_path)
        if not filters.enabled:
            return jobs
        filtered_jobs = filters.apply(jobs)
        self.view.info(f"[bold]Filtro:[/] {len(filtered_jobs)}/{len(jobs)} vagas consideradas")
        logger.bind(
            component="job_search_service",
            portal=self.adapter.name,
            filters_path=filters_path,
            jobs_before=len(jobs),
            jobs_after=len(filtered_jobs),
        ).info("jobs_filtered")
        self._publish_event(
            SearchEventName.JOBS_FILTERED,
            f"Filtro manteve {len(filtered_jobs)}/{len(jobs)} vagas",
            filters_path=filters_path,
            jobs_before=len(jobs),
            jobs_after=len(filtered_jobs),
        )
        if not filtered_jobs:
            self.view.warn("Nenhuma vaga passou no filtro informado.")
        return filtered_jobs

    def _publish_event(self, name: str | SearchEventName, message: str, level: str = "info", **payload) -> None:
        event_payload = {"portal": self.adapter.name, **payload}
        self.event_publisher.publish(SearchEvent(name=name, message=message, level=level, payload=event_payload))
