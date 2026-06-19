from __future__ import annotations

from .job_search.domain import (
    BridgeEndpoint,
    HttpResponse,
    JobDetails,
    JobPosting,
    JobSummary,
    LocationOption,
    SearchQuery,
    SearchResult,
)
from .job_search.domain.filters import JobFilterSet
from .job_search.proxy_sources import DEFAULT_PROVIDER, PROXY_PROVIDERS, resolve_proxy_sources

__all__ = [
    "BridgeEndpoint",
    "HttpResponse",
    "JobDetails",
    "JobFilterSet",
    "JobFinder",
    "JobPosting",
    "JobSummary",
    "LocationOption",
    "SearchQuery",
    "SearchResult",
    "SilentView",
    "InMemoryRepository",
]

class SilentView:
    def info(self, message: str) -> None:
        pass

    def warn(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass

    def choose_location(self, options: list[LocationOption], selected_index: int | None) -> LocationOption:
        if not options:
            raise RuntimeError("Nenhuma localizacao retornada pelo portal.")
        index = (selected_index or 1) - 1
        return options[max(0, min(index, len(options) - 1))]

    def show_jobs(self, jobs: list[JobSummary], limit: int) -> None:
        pass

    def show_job_details(self, jobs: list[JobPosting], limit: int) -> None:
        pass


class InMemoryRepository:
    def __init__(self) -> None:
        self.summaries: list[JobSummary] = []
        self.postings: list[JobPosting] = []

    def save_raw(self, output_path: str, text: str) -> None:
        pass

    def save_jobs(self, output_path: str, jobs: list[JobPosting] | list[JobSummary]) -> None:
        if jobs and isinstance(jobs[0], JobPosting):
            self.postings = list(jobs)
        else:
            self.summaries = list(jobs)


class _CustomFilterRepository:
    def __init__(self, filter_set: JobFilterSet | None = None) -> None:
        self.filter_set = filter_set

    def load(self, filter_path: str | None) -> JobFilterSet:
        if self.filter_set is not None:
            return self.filter_set
        from .job_search.infrastructure.json_filter_repository import JsonJobFilterRepository
        return JsonJobFilterRepository().load(filter_path)


class JobFinder:
    PORTALS = ("linkedin", "gupy", "glassdoor")

    def __init__(
        self,
        portal: str = "linkedin",
        keywords: str = "Vagas",
        location: str = "Brasil",
        *,
        location_id: str | None = None,
        location_choice: int | None = None,
        proxy_sources: list[str] | None = None,
        proxy_provider: str = DEFAULT_PROVIDER,
        valid_count: int = 25,
        jobs_per_proxy: int = 5,
        max_count: int = 177,
        threads: int = 8,
        timeout: float = 12.0,
        detail_timeout: float = 5.0,
        filters: JobFilterSet | str | None = None,
        filters_path: str | None = None,
        details_limit: int = 0,
        start: int = 0,
        max_jobs: int = 0,
        detail_threads: int = 5,
        gd_cookie: str = "",
        silent: bool = True,
    ):
        from dependency_injector import providers

        from .job_search.container import JobSearchContainer
        from .job_search.infrastructure.proxy_pool import ProxyFrameworkPool

        if portal not in self.PORTALS:
            raise ValueError(
                f"Portal invalido: {portal}. Opcoes: {', '.join(self.PORTALS)}"
            )

        proxy_sources = resolve_proxy_sources(proxy_provider, proxy_sources)

        self._proxy_sources = proxy_sources
        self._portal = portal
        self._keywords = keywords
        self._location = location
        self._location_id = location_id
        self._location_choice = location_choice
        self._valid_count = valid_count
        self._jobs_per_proxy = jobs_per_proxy
        self._max_count = max_count
        self._threads = threads
        self._timeout = timeout
        self._detail_timeout = detail_timeout
        self._details_limit = details_limit
        self._start = start
        self._max_jobs = max_jobs
        self._detail_threads = detail_threads
        self._gd_cookie = gd_cookie
        self._silent = silent

        if isinstance(filters, JobFilterSet):
            self._filters_path: str | None = None
            self._filter_set: JobFilterSet | None = filters
        elif isinstance(filters, str):
            self._filters_path = filters
            self._filter_set = None
        elif isinstance(filters_path, str):
            self._filters_path = filters_path
            self._filter_set = None
        else:
            self._filters_path = None
            self._filter_set = None

        self._container = JobSearchContainer()
        self._container.config.portal_name.from_value(portal)
        self._container.config.provider_name.from_value(proxy_provider)
        self._container.config.gd_cookie.from_value(gd_cookie)

        self._view = SilentView()
        self._repository = InMemoryRepository()
        self._filter_repo = _CustomFilterRepository(self._filter_set)
        self._container.view.override(providers.Object(self._view))
        self._container.repository.override(providers.Object(self._repository))
        self._container.filter_repository.override(providers.Object(self._filter_repo))
        self._container.proxy_pool.override(
            providers.Factory(
                ProxyFrameworkPool,
                provider_name=proxy_provider,
                use_console=not silent,
            )
        )

        self._service = self._container.job_search_service()

    def search(
        self,
        *,
        jobs_output: str | None = None,
        details_output: str | None = None,
        filters: JobFilterSet | str | None = None,
    ) -> list[JobPosting]:
        from .job_search.service import JobSearchRequest

        if isinstance(filters, JobFilterSet):
            self._filter_repo.filter_set = filters
            effective_filters_path: str | None = None
        elif isinstance(filters, str):
            self._filter_repo.filter_set = None
            effective_filters_path = filters
        else:
            self._filter_repo.filter_set = self._filter_set
            effective_filters_path = self._filters_path

        if jobs_output is None:
            jobs_output = f"output/{self._portal}/vagas.json"
        if details_output is None:
            details_output = f"output/{self._portal}/detalhadas.json"

        request = JobSearchRequest(
            proxy_sources=self._proxy_sources,
            keywords=self._keywords,
            location=self._location,
            location_id=self._location_id,
            location_choice=self._location_choice,
            valid_count=self._valid_count,
            jobs_per_proxy=self._jobs_per_proxy,
            max_count=self._max_count,
            threads=self._threads,
            timeout=self._timeout,
            detail_timeout=self._detail_timeout,
            jobs_output=jobs_output,
            details_output=details_output,
            filters_path=effective_filters_path,
            details_limit=self._details_limit,
            show_jobs=0,
            start=self._start,
            max_jobs=self._max_jobs,
            detail_threads=self._detail_threads,
        )

        self._service.run(request)
        return self._repository.postings or [
            JobPosting(summary=s) for s in self._repository.summaries
        ]
