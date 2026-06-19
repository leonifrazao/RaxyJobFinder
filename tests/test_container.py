from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from dependency_injector import providers, errors

from job_search.container import JobSearchContainer


@pytest.fixture
def container() -> JobSearchContainer:
    c = JobSearchContainer()
    c.config.portal_name.from_value("linkedin")
    c.config.provider_name.from_value("test_provider")
    c.config.gd_cookie.from_value("")
    return c


class TestConfig:
    def test_defaults_are_undefined(self):
        c = JobSearchContainer()
        assert c.config.portal_name() is None

    def test_set_config_values(self, container: JobSearchContainer):
        assert container.config.portal_name() == "linkedin"
        assert container.config.provider_name() == "test_provider"
        assert container.config.gd_cookie() == ""

    def test_override_config_after_instantiation(self):
        c = JobSearchContainer()
        c.config.portal_name.from_value("gupy")
        c.config.provider_name.from_value("brasil")
        c.config.gd_cookie.from_value("cookie")
        assert c.config.portal_name() == "gupy"
        assert c.config.provider_name() == "brasil"
        assert c.config.gd_cookie() == "cookie"


class TestProviders:
    def test_http_client_provider(self, container: JobSearchContainer):
        client = container.http_client()
        from job_search.infrastructure.http.botasaurus_http_client import BotasaurusHttpClient
        assert isinstance(client, BotasaurusHttpClient)

    def test_view_provider(self, container: JobSearchContainer):
        view = container.view()
        from job_search.interfaces.console.rich_job_search_view import RichJobSearchView
        assert isinstance(view, RichJobSearchView)

    def test_view_is_singleton(self, container: JobSearchContainer):
        v1 = container.view()
        v2 = container.view()
        assert v1 is v2

    def test_repository_provider(self, container: JobSearchContainer):
        repo = container.repository()
        from job_search.infrastructure.persistence.json_job_repository import JsonJobRepository
        assert isinstance(repo, JsonJobRepository)

    def test_filter_repository_provider(self, container: JobSearchContainer):
        repo = container.filter_repository()
        from job_search.infrastructure.persistence.json_job_filter_repository import JsonJobFilterRepository
        assert isinstance(repo, JsonJobFilterRepository)

    def test_proxy_pool_provider(self, container: JobSearchContainer):
        pool = container.proxy_pool()
        from job_search.infrastructure.proxy.proxy_framework_pool import ProxyFrameworkPool
        assert isinstance(pool, ProxyFrameworkPool)

    def test_proxy_pool_passes_config(self, container: JobSearchContainer):
        from job_search.infrastructure.config import load_settings
        pool = container.proxy_pool()
        assert pool.provider_name == "test_provider"
        assert pool.use_console is (load_settings().defaults.silent is False)


class TestAdapterSelector:
    def test_linkedin_adapter(self, container: JobSearchContainer):
        adapter = container.linkedin_adapter()
        from job_search.providers.job_boards.linkedin import LinkedInJobBoardAdapter
        assert isinstance(adapter, LinkedInJobBoardAdapter)

    def test_gupy_adapter(self, container: JobSearchContainer):
        adapter = container.gupy_adapter()
        from job_search.providers.job_boards.gupy import GupyJobBoardAdapter
        assert isinstance(adapter, GupyJobBoardAdapter)

    def test_glassdoor_adapter(self, container: JobSearchContainer):
        adapter = container.glassdoor_adapter()
        from job_search.providers.job_boards.glassdoor import GlassdoorJobBoardAdapter
        assert isinstance(adapter, GlassdoorJobBoardAdapter)

    def test_selector_returns_linkedin(self, container: JobSearchContainer):
        adapter = container.job_board_adapter()
        from job_search.providers.job_boards.linkedin import LinkedInJobBoardAdapter
        assert isinstance(adapter, LinkedInJobBoardAdapter)

    def test_selector_returns_gupy(self):
        c = JobSearchContainer()
        c.config.portal_name.from_value("gupy")
        c.config.provider_name.from_value("p")
        c.config.gd_cookie.from_value("")
        adapter = c.job_board_adapter()
        from job_search.providers.job_boards.gupy import GupyJobBoardAdapter
        assert isinstance(adapter, GupyJobBoardAdapter)

    def test_selector_returns_glassdoor(self):
        c = JobSearchContainer()
        c.config.portal_name.from_value("glassdoor")
        c.config.provider_name.from_value("p")
        c.config.gd_cookie.from_value("")
        adapter = c.job_board_adapter()
        from job_search.providers.job_boards.glassdoor import GlassdoorJobBoardAdapter
        assert isinstance(adapter, GlassdoorJobBoardAdapter)

    def test_selector_unknown_portal_raises(self):
        c = JobSearchContainer()
        c.config.portal_name.from_value("unknown_portal")
        c.config.provider_name.from_value("p")
        c.config.gd_cookie.from_value("")
        with pytest.raises(errors.Error, match="no .*unknown_portal"):
            c.job_board_adapter()


class TestServiceWiring:
    def test_service_provider(self, container: JobSearchContainer):
        mock_proxy = MagicMock()
        with container.proxy_pool.override(providers.Factory(lambda: mock_proxy)):
            service = container.job_search_service()
        from job_search.application.job_search_service import JobSearchService
        assert isinstance(service, JobSearchService)

    def test_service_injects_dependencies(self, container: JobSearchContainer):
        mock_proxy = MagicMock()
        with container.proxy_pool.override(providers.Factory(lambda: mock_proxy)):
            service = container.job_search_service()
        assert service.adapter is not None
        assert service.repository is not None
        assert service.view is not None
