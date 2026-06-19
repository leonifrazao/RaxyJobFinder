from __future__ import annotations

from dependency_injector import containers, providers

from job_search.application import BridgeSearchService, DefaultSearchEventReporter, JobDetailingService, JobSearchService, SearchResultSaver
from job_search.infrastructure.http.botasaurus_http_client import BotasaurusHttpClient
from job_search.infrastructure.messaging import build_search_event_publisher
from job_search.infrastructure.persistence.json_job_filter_repository import JsonJobFilterRepository
from job_search.infrastructure.persistence.json_job_repository import JsonJobRepository
from job_search.infrastructure.proxy.proxy_framework_pool import ProxyFrameworkPool
from job_search.interfaces.console.rich_job_search_view import RichJobSearchView
from job_search.providers.job_boards.glassdoor import GlassdoorJobBoardAdapter
from job_search.providers.job_boards.gupy import GupyJobBoardAdapter
from job_search.providers.job_boards.linkedin import LinkedInJobBoardAdapter


class JobSearchContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    http_client = providers.Factory(BotasaurusHttpClient)
    view = providers.Singleton(RichJobSearchView)
    repository = providers.Factory(JsonJobRepository)
    filter_repository = providers.Factory(JsonJobFilterRepository)
    event_publisher = providers.Factory(
        build_search_event_publisher,
        redis_url=config.redis_url,
        channel=config.events_channel,
    )
    proxy_pool = providers.Factory(
        ProxyFrameworkPool,
        provider_name=config.provider_name,
        use_console=config.use_console,
    )

    linkedin_adapter = providers.Factory(
        LinkedInJobBoardAdapter,
        http_client=http_client,
    )

    gupy_adapter = providers.Factory(
        GupyJobBoardAdapter,
        http_client=http_client,
    )

    glassdoor_adapter = providers.Factory(
        GlassdoorJobBoardAdapter,
        http_client=http_client,
        cookie_string=config.gd_cookie,
    )

    job_board_adapter = providers.Selector(
        config.portal_name,
        linkedin=linkedin_adapter,
        gupy=gupy_adapter,
        glassdoor=glassdoor_adapter,
    )

    event_reporter = providers.Factory(
        DefaultSearchEventReporter,
        adapter=job_board_adapter,
        event_publisher=event_publisher,
    )

    bridge_search = providers.Factory(
        BridgeSearchService,
        adapter=job_board_adapter,
        view=view,
        event_reporter=event_reporter,
    )

    job_detailing = providers.Factory(
        JobDetailingService,
        adapter=job_board_adapter,
        view=view,
        event_reporter=event_reporter,
    )

    result_saver = providers.Factory(
        SearchResultSaver,
        repository=repository,
        view=view,
        event_reporter=event_reporter,
    )

    job_search_service = providers.Factory(
        JobSearchService,
        adapter=job_board_adapter,
        proxy_pool=proxy_pool,
        filter_repository=filter_repository,
        view=view,
        bridge_search=bridge_search,
        job_detailing=job_detailing,
        result_saver=result_saver,
        event_reporter=event_reporter,
    )
