from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from buscador_vagas import (
    InMemoryRepository,
    JobDetails,
    JobFilterSet,
    JobFinder,
    JobPosting,
    JobSummary,
    LocationOption,
    SilentView,
)
from job_search.application.dto.input.job_search_request import JobSearchRequest


@pytest.fixture
def mock_deps():
    container = MagicMock()
    container.config.portal_name = MagicMock()
    container.config.provider_name = MagicMock()
    container.config.gd_cookie = MagicMock()
    container.view = MagicMock()
    container.repository = MagicMock()
    container.proxy_pool = MagicMock()
    mock_service = MagicMock()
    container.job_search_service = MagicMock(return_value=mock_service)

    mock_container_module = MagicMock()
    mock_container_module.JobSearchContainer = MagicMock(return_value=container)

    mock_proxy_framework = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "job_search.container": mock_container_module,
            "job_search.infrastructure.proxy.proxy_framework_pool": mock_proxy_framework,
        },
    ):
        yield container, mock_service


class TestSilentView:
    def test_info_does_nothing(self):
        view = SilentView()
        assert view.info("test") is None

    def test_warn_does_nothing(self):
        view = SilentView()
        assert view.warn("test") is None

    def test_error_does_nothing(self):
        view = SilentView()
        assert view.error("test") is None

    def test_show_jobs_does_nothing(self):
        view = SilentView()
        assert view.show_jobs([], 10) is None

    def test_show_job_details_does_nothing(self):
        view = SilentView()
        assert view.show_job_details([], 10) is None

    def test_choose_location_selects_first(self):
        view = SilentView()
        options = [LocationOption("1", "SP"), LocationOption("2", "RJ")]
        result = view.choose_location(options, None)
        assert result.id == "1"

    def test_choose_location_respects_index(self):
        view = SilentView()
        options = [LocationOption("1", "SP"), LocationOption("2", "RJ")]
        result = view.choose_location(options, 2)
        assert result.id == "2"

    def test_choose_location_raises_on_empty(self):
        view = SilentView()
        with pytest.raises(RuntimeError):
            view.choose_location([], None)

    def test_choose_location_clamps_out_of_range(self):
        view = SilentView()
        options = [LocationOption("1", "SP")]
        result = view.choose_location(options, 999)
        assert result.id == "1"


class TestInMemoryRepository:
    def test_initial_state(self):
        repo = InMemoryRepository()
        assert repo.summaries == []
        assert repo.postings == []

    def test_save_raw_does_nothing(self):
        repo = InMemoryRepository()
        assert repo.save_raw("path", "text") is None

    def test_save_jobs_summaries(self):
        repo = InMemoryRepository()
        jobs = [JobSummary("linkedin", "e1", "Dev")]
        repo.save_jobs("out.json", jobs)
        assert repo.summaries == jobs
        assert repo.postings == []

    def test_save_jobs_postings(self):
        repo = InMemoryRepository()
        postings = [JobPosting(summary=JobSummary("linkedin", "e1", "Dev"))]
        repo.save_jobs("out.json", postings)
        assert repo.postings == postings
        assert repo.summaries == []

    def test_save_jobs_empty_list(self):
        repo = InMemoryRepository()
        repo.save_jobs("out.json", [])
        assert repo.summaries == []
        assert repo.postings == []


class TestJobFinder:
    def test_default_creation(self, mock_deps):
        container, _ = mock_deps
        finder = JobFinder()

        assert finder._portal == "linkedin"
        assert finder._keywords == "Vagas"
        assert finder._location == "Brasil"
        assert container.config.portal_name.from_value.called

    def test_custom_portal(self, mock_deps):
        container, _ = mock_deps
        finder = JobFinder(portal="gupy")

        assert finder._portal == "gupy"

    def test_invalid_portal(self, mock_deps):
        with pytest.raises(ValueError, match="invalido"):
            JobFinder(portal="indeed")

    def test_custom_keywords_and_location(self, mock_deps):
        finder = JobFinder(keywords="Data Science", location="São Paulo")

        assert finder._keywords == "Data Science"
        assert finder._location == "São Paulo"

    def test_custom_proxy_sources(self, mock_deps):
        finder = JobFinder(proxy_sources=["http://custom.proxy:8080"])

        assert finder._proxy_sources == ["http://custom.proxy:8080"]

    def test_search_returns_postings(self, mock_deps):
        container, mock_service = mock_deps
        finder = JobFinder()
        expected = [JobPosting(summary=JobSummary("linkedin", "e1", "Dev"))]
        finder._repository.postings = expected

        result = finder.search()

        assert result == expected
        mock_service.run.assert_called_once()

    def test_search_falls_back_to_summaries(self, mock_deps):
        mock_deps
        finder = JobFinder()
        summaries = [JobSummary("linkedin", "e1", "Dev")]
        finder._repository.postings = []
        finder._repository.summaries = summaries

        result = finder.search()

        assert len(result) == 1
        assert result[0].summary == summaries[0]

    def test_search_includes_request_params(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(
            portal="gupy",
            keywords="Python",
            location="SP",
            timeout=30.0,
            details_limit=10,
        )
        finder.search()

        call_args = mock_service.run.call_args[0][0]
        assert isinstance(call_args, JobSearchRequest)
        assert call_args.keywords == "Python"
        assert call_args.location == "SP"
        assert call_args.timeout == 30.0
        assert call_args.details_limit == 10
        assert call_args.show_jobs == 0

    def test_search_custom_output_paths(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder()
        finder.search(
            jobs_output="custom/jobs.json", details_output="custom/details.json"
        )

        request = mock_service.run.call_args[0][0]
        assert request.jobs_output == "custom/jobs.json"
        assert request.details_output == "custom/details.json"

    def test_gd_cookie_passed_to_container(self, mock_deps):
        container, _ = mock_deps
        JobFinder(portal="glassdoor", gd_cookie="my-cookie")

        container.config.gd_cookie.from_value.assert_called_with("my-cookie")

    def test_default_output_paths(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(portal="linkedin")
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.jobs_output == "output/linkedin/vagas.json"
        assert request.details_output == "output/linkedin/detalhadas.json"

    def test_location_id_passed_through(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(location_id="106057199")
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.location_id == "106057199"

    def test_work_type_passed_through(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(work_type="remote")
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.work_type == "remote"

    def test_under_10_applicants_passed_through(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(under_10_applicants=True)
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.under_10_applicants is True

    def test_filters_path_string_in_init(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(filters="filters/python.json")
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.filters_path == "filters/python.json"
        assert finder._filter_set is None

    def test_filters_jobfilterset_in_init(self, mock_deps):
        _, mock_service = mock_deps
        fs = JobFilterSet.accept_all()
        finder = JobFinder(filters=fs)
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.filters_path is None
        assert finder._filter_set is fs
        assert finder._filter_repo.filter_set is fs

    def test_filters_in_search_overrides_init(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(filters="filters/default.json")
        fs = JobFilterSet.accept_all()
        finder.search(filters=fs)

        request = mock_service.run.call_args[0][0]
        assert request.filters_path is None
        assert finder._filter_repo.filter_set is fs

    def test_filters_path_backward_compat(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder(filters_path="filters/legacy.json")
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.filters_path == "filters/legacy.json"
        assert finder._filter_set is None

    def test_filters_takes_precedence_over_filters_path(self, mock_deps):
        _, mock_service = mock_deps
        fs = JobFilterSet.accept_all()
        finder = JobFinder(filters=fs, filters_path="filters/ignored.json")
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.filters_path is None
        assert finder._filter_repo.filter_set is fs

    def test_search_string_filters(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder()
        finder.search(filters="filters/search.json")

        request = mock_service.run.call_args[0][0]
        assert request.filters_path == "filters/search.json"

    def test_no_filters_by_default(self, mock_deps):
        _, mock_service = mock_deps
        finder = JobFinder()
        finder.search()

        request = mock_service.run.call_args[0][0]
        assert request.filters_path is None
        assert finder._filter_set is None
        assert finder._filter_repo.filter_set is None
