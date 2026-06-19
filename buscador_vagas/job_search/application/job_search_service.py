from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.application.ports.job_board_adapter import JobBoardAdapter
from job_search.application.ports.job_filter_repository import JobFilterRepository
from job_search.application.ports.job_repository import JobRepository
from job_search.application.ports.job_search_view import JobSearchView
from job_search.application.ports.proxy_pool import ProxyPool
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
    ) -> None:
        self.adapter = adapter
        self.proxy_pool = proxy_pool
        self.repository = repository
        self.filter_repository = filter_repository
        self.view = view

    def run(self, request: JobSearchRequest) -> int:
        query = SearchQuery(request.keywords, request.location, request.location_id)
        bridges = self._prepare_bridges(query, request)
        try:
            query = self._resolve_location(query, bridges, request)
            result = self._search_with_first_working_bridge(query, bridges, request.timeout, request.max_jobs, request.start)
            if result is None:
                self.view.error("Nenhuma bridge conseguiu retornar resposta do portal.")
                return 1

            if not result.jobs:
                self.view.warn("Nenhuma vaga encontrada.")
                self.repository.save_jobs(request.jobs_output, [])
                self.repository.save_jobs(request.details_output, [])
                return 0

            self.view.show_jobs(result.jobs, request.show_jobs)
            detailed_jobs = self._enrich_jobs(result.jobs, bridges, result.search_url, request)
            filtered_jobs = self._filter_jobs(detailed_jobs, request.filters_path)

            self.repository.save_jobs(request.jobs_output, [job.summary for job in filtered_jobs])
            self.view.info(f"[bold green]Vagas salvas em:[/] {request.jobs_output}")
            self.repository.save_jobs(request.details_output, filtered_jobs)
            self.view.info(f"[bold green]Vagas detalhadas salvas em:[/] {request.details_output}")
            self.view.show_job_details(filtered_jobs, request.show_jobs)
            return 0
        finally:
            self.proxy_pool.stop()

    def _prepare_bridges(self, query: SearchQuery, request: JobSearchRequest) -> list[BridgeEndpoint]:
        test_url = self.adapter.build_search_url(query)
        bridges = self.proxy_pool.prepare(
            sources=request.proxy_sources,
            max_count=request.max_count,
            valid_count=request.valid_count,
            threads=request.threads,
            timeout=request.timeout,
            test_url=test_url,
        )
        self.view.info(f"[bold]Bridges ativas:[/] {len(bridges)}")
        self.view.info(f"[bold]Rotacao de detalhes:[/] 1 proxy a cada {max(1, request.jobs_per_proxy)} vagas")
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
                self.view.warn(f"Typeahead falhou na bridge {bridge.index}: {exc}")
                continue
            return query.with_location(self.view.choose_location(options, request.location_choice))
        raise RuntimeError("Nenhuma bridge conseguiu consultar opcoes de localizacao.")

    def _search_with_first_working_bridge(self, query: SearchQuery, bridges: list[BridgeEndpoint], timeout: float, max_jobs: int = 0, start: int = 0):
        for bridge in bridges:
            self.view.info(f"[bold]Testando {self.adapter.name} via bridge {bridge.index}:[/] {bridge.url}")
            try:
                result = self.adapter.search_jobs(bridge.url, query, timeout, max_jobs=max_jobs, start=start)
            except Exception as exc:
                self.view.warn(f"Bridge {bridge.index} falhou no request: {exc}")
                continue
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
                self.view.warn(f"Bridge {bridge.index} falhou no detalhe {job.external_id}; tentando proxima: {exc}")
        self.view.error(f"Falha ao detalhar {job.external_id}: {last_error}")
        return session.failed_detail(job, last_error)

    def _filter_jobs(self, jobs: list[JobPosting], filters_path: str | None) -> list[JobPosting]:
        filters = self.filter_repository.load(filters_path)
        if not filters.enabled:
            return jobs
        filtered_jobs = filters.apply(jobs)
        self.view.info(f"[bold]Filtro:[/] {len(filtered_jobs)}/{len(jobs)} vagas consideradas")
        if not filtered_jobs:
            self.view.warn("Nenhuma vaga passou no filtro informado.")
        return filtered_jobs
