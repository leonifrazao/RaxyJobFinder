from __future__ import annotations

from typing import Protocol

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.application.dto.output.search_result import SearchResult
from job_search.domain.proxy import BridgeEndpoint
from job_search.domain.search_query import SearchQuery


class BridgeSearch(Protocol):
    def resolve_location(self, query: SearchQuery, bridges: list[BridgeEndpoint], request: JobSearchRequest) -> SearchQuery:
        ...

    def search_with_first_working_bridge(
        self,
        query: SearchQuery,
        bridges: list[BridgeEndpoint],
        timeout: float,
        max_jobs: int = 0,
        start: int = 0,
    ) -> SearchResult | None:
        ...
