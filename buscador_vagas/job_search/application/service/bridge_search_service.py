from __future__ import annotations

from loguru import logger

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.application.dto.output.search_result import SearchResult
from job_search.application.events.search_event import SearchEventName
from job_search.application.ports import BridgeSearch, JobBoardAdapter, JobSearchView, SearchEventReporter
from job_search.domain.proxy import BridgeEndpoint
from job_search.domain.search_query import SearchQuery
from job_search.domain.text import clean_text


class BridgeSearchService(BridgeSearch):
    def __init__(self, adapter: JobBoardAdapter, view: JobSearchView, event_reporter: SearchEventReporter) -> None:
        self.adapter = adapter
        self.view = view
        self.event_reporter = event_reporter

    def resolve_location(self, query: SearchQuery, bridges: list[BridgeEndpoint], request: JobSearchRequest) -> SearchQuery:
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
                self.event_reporter.publish(
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
            self.event_reporter.publish(
                SearchEventName.LOCATION_RESOLVED,
                f"Localizacao selecionada: {selected.name}",
                location_id=selected.id,
                location_name=selected.name,
            )
            return query.with_location(selected)
        raise RuntimeError("Nenhuma bridge conseguiu consultar opcoes de localizacao.")

    def search_with_first_working_bridge(
        self,
        query: SearchQuery,
        bridges: list[BridgeEndpoint],
        timeout: float,
        max_jobs: int = 0,
        start: int = 0,
    ) -> SearchResult | None:
        for bridge in bridges:
            logger.bind(
                component="job_search_service",
                portal=self.adapter.name,
                bridge_index=bridge.index,
            ).info("search_bridge_attempt")
            self.event_reporter.publish(SearchEventName.SEARCH_BRIDGE_ATTEMPT, f"Testando bridge {bridge.index}", bridge_index=bridge.index)
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
                self.event_reporter.publish(
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
            self.event_reporter.publish(
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
