from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from loguru import logger

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
from job_search.domain.text import clean_text


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
        self.repository.save_jobs(request.jobs_output, [])
        self.repository.save_jobs(request.details_output, [])
        return 0

    def _save_results(self, request: JobSearchRequest, filtered_jobs: list[JobPosting]) -> None:
        self._publish_event(SearchEventName.SAVE_STARTED, "Salvando vagas...")
        self.repository.save_jobs(request.jobs_output, [job.summary for job in filtered_jobs])
        self.view.info(f"[bold green]Vagas salvas em:[/] {request.jobs_output}")
        self._publish_event(SearchEventName.SAVE_DETAILS_STARTED, "Salvando detalhes...")
        self.repository.save_jobs(request.details_output, filtered_jobs)
        self.view.info(f"[bold green]Vagas detalhadas salvas em:[/] {request.details_output}")
        self._publish_event(SearchEventName.SAVE_FINISHED, "Resultados salvos", jobs_output=request.jobs_output, details_output=request.details_output)

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
        if query.location_id:
            return query
        if not clean_text(query.location):
            return query
        for bridge in bridges:
            try:
                options = self.adapter.get_location_options(bridge.url, query.location, request.timeout)
            except Exception as exc:
                logger.bind(
                    component="job_search_service",
                    portal=self.adapter.name,
                    bridge_index=bridge.index,
                    error=str(exc),
                ).warning("location_typeahead_failed")
                self._publish_event(
                    SearchEventName.LOCATION_TYPEAHEAD_FAILED,
                    f"Typeahead falhou na bridge {bridge.index}",
                    level="warning",
                    bridge_index=bridge.index,
                    error=str(exc),
                )
                self.view.warn(f"Typeahead falhou na bridge {bridge.index}: {exc}")
                continue
            selected = self.view.choose_location(options, request.location_choice)
            logger.bind(
                component="job_search_service",
                portal=self.adapter.name,
                location_id=selected.id,
                location_name=selected.name,
            ).info("location_resolved")
            self._publish_event(
                SearchEventName.LOCATION_RESOLVED,
                f"Localizacao selecionada: {selected.name}",
                location_id=selected.id,
                location_name=selected.name,
            )
            return query.with_location(selected)
        raise RuntimeError("Nenhuma bridge conseguiu consultar opcoes de localizacao.")

    def _search_with_first_working_bridge(self, query: SearchQuery, bridges: list[BridgeEndpoint], timeout: float, max_jobs: int = 0, start: int = 0):
        for bridge in bridges:
            logger.bind(
                component="job_search_service",
                portal=self.adapter.name,
                bridge_index=bridge.index,
            ).info("search_bridge_attempt")
            self._publish_event(SearchEventName.SEARCH_BRIDGE_ATTEMPT, f"Testando bridge {bridge.index}", bridge_index=bridge.index)
            self.view.info(f"[bold]Testando {self.adapter.name} via bridge {bridge.index}:[/] {bridge.url}")
            try:
                result = self.adapter.search_jobs(bridge.url, query, timeout, max_jobs=max_jobs, start=start)
            except Exception as exc:
                logger.bind(
                    component="job_search_service",
                    portal=self.adapter.name,
                    bridge_index=bridge.index,
                    error=str(exc),
                ).warning("search_bridge_failed")
                self._publish_event(
                    SearchEventName.SEARCH_BRIDGE_FAILED,
                    f"Bridge {bridge.index} falhou na busca",
                    level="warning",
                    bridge_index=bridge.index,
                    error=str(exc),
                )
                self.view.warn(f"Bridge {bridge.index} falhou no request: {exc}")
                continue
            logger.bind(
                component="job_search_service",
                portal=self.adapter.name,
                bridge_index=bridge.index,
                status_code=result.response.status_code,
                response_size=len(result.response.text),
                jobs_count=len(result.jobs),
                url=result.response.url,
            ).info("search_bridge_succeeded")
            self._publish_event(
                SearchEventName.SEARCH_BRIDGE_SUCCEEDED,
                f"Bridge {bridge.index} retornou {len(result.jobs)} vagas",
                bridge_index=bridge.index,
                status_code=result.response.status_code,
                jobs_count=len(result.jobs),
                response_size=len(result.response.text),
            )
            self.view.info(f"[bold]Bridge {bridge.index} status:[/] {result.response.status_code}")
            self.view.info(f"[bold]URL final:[/] {result.response.url}")
            self.view.info(f"[bold]Content-Type:[/] {result.response.headers.get('content-type', '-')}")
            self.view.info(f"[bold]Tamanho:[/] {len(result.response.text)} bytes")
            self.view.info(result.response.text[:500].replace("\n", " "))
            return result
        return None

    def _enrich_jobs(self, jobs: list[JobSummary], bridges: list[BridgeEndpoint], search_url: str, request: JobSearchRequest) -> list[JobPosting]:
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
                executor.submit(self._detail_one_job, session, job, i, search_url, request.detail_timeout): i
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

    def _detail_one_job(
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
