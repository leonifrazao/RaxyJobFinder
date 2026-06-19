from __future__ import annotations

from buscador_vagas.job_search.application.dto.input.job_search_request import JobSearchRequest
from buscador_vagas.job_search.domain.filtering import JobFilterSet
from buscador_vagas.job_search.domain.job_posting import JobPosting
from buscador_vagas.job_search.infrastructure.logging import configure_logging
from buscador_vagas.job_search.infrastructure.proxy.proxy_framework_pool import ProxyFrameworkPool
from buscador_vagas.job_search.infrastructure.proxy.proxy_sources import DEFAULT_PROVIDER, resolve_proxy_sources
from buscador_vagas.sdk.custom_filter_repository import _CustomFilterRepository
from buscador_vagas.sdk.in_memory_repository import InMemoryRepository
from buscador_vagas.sdk.silent_view import SilentView


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
        from loguru import logger

        from buscador_vagas.job_search.container import JobSearchContainer
        configure_logging()
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
        logger.bind(
            component="sdk",
            portal=portal,
            provider=proxy_provider,
            proxy_sources_count=len(proxy_sources),
        ).info("sdk_job_finder_created")

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
        from loguru import logger

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

        logger.bind(component="sdk", portal=self._portal, keywords=self._keywords).info("sdk_search_started")
        exit_code = self._service.run(request)
        jobs = self._repository.postings or [
            JobPosting(summary=summary) for summary in self._repository.summaries
        ]
        logger.bind(
            component="sdk",
            portal=self._portal,
            exit_code=exit_code,
            jobs_count=len(jobs),
            jobs_output=jobs_output,
            details_output=details_output,
        ).info("sdk_search_finished")
        return jobs
