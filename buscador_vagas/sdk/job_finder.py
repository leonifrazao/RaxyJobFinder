from __future__ import annotations

import os

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.domain.filtering import JobFilterSet
from job_search.domain.job_posting import JobPosting
from job_search.infrastructure.config import load_settings
from job_search.infrastructure.logging import configure_logging
from job_search.infrastructure.proxy.proxy_framework_pool import ProxyFrameworkPool
from job_search.infrastructure.proxy.proxy_sources import DEFAULT_PROVIDER, resolve_proxy_sources
from buscador_vagas.sdk.custom_filter_repository import _CustomFilterRepository
from buscador_vagas.sdk.in_memory_repository import InMemoryRepository
from buscador_vagas.sdk.silent_view import SilentView


class JobFinder:
    PORTALS = ("linkedin", "gupy", "glassdoor")

    def __init__(
        self,
        portal: str | None = None,
        keywords: str | None = None,
        location: str | None = None,
        *,
        location_id: str | None = None,
        location_choice: int | None = None,
        work_type: str | None = None,
        under_10_applicants: bool | None = None,
        recent_period: str | None = None,
        proxy_sources: list[str] | None = None,
        proxy_provider: str | None = None,
        valid_count: int | None = None,
        jobs_per_proxy: int | None = None,
        max_count: int | None = None,
        threads: int | None = None,
        timeout: float | None = None,
        detail_timeout: float | None = None,
        filters: JobFilterSet | str | None = None,
        filters_path: str | None = None,
        details_limit: int | None = None,
        start: int | None = None,
        max_jobs: int | None = None,
        detail_threads: int | None = None,
        gd_cookie: str | None = None,
        silent: bool | None = None,
        view: object | None = None,
        filter_by_keywords: bool | None = None,
    ):
        from dependency_injector import providers
        from loguru import logger

        from job_search.container import JobSearchContainer

        cfg = load_settings().defaults

        portal = portal or cfg.portal
        keywords = keywords or cfg.keywords
        location = location or cfg.location
        location_id = location_id or cfg.location_id or None
        location_choice = location_choice or cfg.location_choice or None
        work_type = work_type or cfg.work_type or None
        under_10_applicants = under_10_applicants if under_10_applicants is not None else cfg.under_10_applicants
        recent_period = recent_period or cfg.recent_period or "any"
        proxy_provider = proxy_provider or DEFAULT_PROVIDER
        valid_count = valid_count if valid_count is not None else cfg.valid_count
        jobs_per_proxy = jobs_per_proxy if jobs_per_proxy is not None else cfg.jobs_per_proxy
        max_count = max_count if max_count is not None else cfg.max_count
        threads = threads if threads is not None else cfg.threads
        timeout = timeout if timeout is not None else cfg.timeout
        detail_timeout = detail_timeout if detail_timeout is not None else cfg.detail_timeout
        details_limit = details_limit if details_limit is not None else cfg.details_limit
        start = start if start is not None else cfg.start
        max_jobs = max_jobs if max_jobs is not None else cfg.max_jobs
        detail_threads = detail_threads if detail_threads is not None else cfg.detail_threads
        gd_cookie = gd_cookie if gd_cookie is not None else cfg.gd_cookie
        silent = silent if silent is not None else cfg.silent
        filter_by_keywords = filter_by_keywords if filter_by_keywords is not None else False

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
        self._work_type = work_type
        self._under_10_applicants = under_10_applicants
        self._recent_period = recent_period
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

        redis_cfg = load_settings().redis

        self._filter_by_keywords = filter_by_keywords
        self._container = JobSearchContainer()
        self._container.config.portal_name.from_value(portal)
        self._container.config.provider_name.from_value(proxy_provider)
        self._container.config.gd_cookie.from_value(gd_cookie)
        self._container.config.redis_url.from_value(os.getenv("RAXY_REDIS_URL", redis_cfg.url))
        self._container.config.events_channel.from_value(os.getenv("RAXY_REDIS_CHANNEL", redis_cfg.channel))
        self._container.config.use_console.from_value(not silent)
        logger.bind(
            component="sdk",
            portal=portal,
            provider=proxy_provider,
            proxy_sources_count=len(proxy_sources),
        ).info("sdk_job_finder_created")

        self._view = view or SilentView()
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
        max_jobs: int | None = None,
        details_limit: int | None = None,
        start: int | None = None,
        detail_threads: int | None = None,
    ) -> list[JobPosting]:
        from loguru import logger

        output_cfg = load_settings().output

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
            jobs_output = output_cfg.jobs_path.format(portal=self._portal)
        if details_output is None:
            details_output = output_cfg.details_path.format(portal=self._portal)

        request = JobSearchRequest(
            proxy_sources=self._proxy_sources,
            keywords=self._keywords,
            location=self._location,
            location_id=self._location_id,
            location_choice=self._location_choice,
            work_type=self._work_type,
            under_10_applicants=self._under_10_applicants,
            recent_period=self._recent_period,
            valid_count=self._valid_count,
            jobs_per_proxy=self._jobs_per_proxy,
            max_count=self._max_count,
            threads=self._threads,
            timeout=self._timeout,
            detail_timeout=self._detail_timeout,
            jobs_output=jobs_output,
            details_output=details_output,
            filters_path=effective_filters_path,
            details_limit=details_limit if details_limit is not None else self._details_limit,
            show_jobs=0,
            start=start if start is not None else self._start,
            max_jobs=max_jobs if max_jobs is not None else self._max_jobs,
            detail_threads=detail_threads if detail_threads is not None else self._detail_threads,
            filter_by_keywords=self._filter_by_keywords,
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
