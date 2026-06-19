from __future__ import annotations

from dependency_injector import containers, providers

from job_search.infrastructure.http_client import BotasaurusHttpClient
from job_search.infrastructure.json_filter_repository import JsonJobFilterRepository
from job_search.infrastructure.json_repository import JsonJobRepository
from job_search.infrastructure.proxy_pool import ProxyFrameworkPool
from job_search.modules.glassdoor import GlassdoorJobBoardAdapter
from job_search.modules.gupy import GupyJobBoardAdapter
from job_search.modules.linkedin import LinkedInJobBoardAdapter
from job_search.application import JobSearchService
from job_search.view import RichJobSearchView


class JobSearchContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    http_client = providers.Factory(BotasaurusHttpClient)
    view = providers.Singleton(RichJobSearchView)
    repository = providers.Factory(JsonJobRepository)
    filter_repository = providers.Factory(JsonJobFilterRepository)
    proxy_pool = providers.Factory(
        ProxyFrameworkPool,
        provider_name=config.provider_name,
        use_console=True,
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

    job_search_service = providers.Factory(
        JobSearchService,
        adapter=job_board_adapter,
        proxy_pool=proxy_pool,
        repository=repository,
        filter_repository=filter_repository,
        view=view,
    )
