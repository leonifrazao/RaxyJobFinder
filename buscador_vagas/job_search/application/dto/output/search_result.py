from __future__ import annotations

from dataclasses import dataclass

from job_search.application.dto.output.http_response import HttpResponse
from job_search.domain.job_summary import JobSummary
from job_search.domain.search_query import SearchQuery


@dataclass(frozen=True)
class SearchResult:
    query: SearchQuery
    search_url: str
    response: HttpResponse
    jobs: list[JobSummary]
