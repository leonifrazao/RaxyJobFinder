from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.application.service.bridge_search_service import BridgeSearchService
from job_search.application.service.job_detailing_service import JobDetailingService
from job_search.application.service.job_search_service import JobSearchService
from job_search.application.service.search_event_reporter import DefaultSearchEventReporter
from job_search.application.service.search_result_saver import SearchResultSaver
from job_search.domain.job_details import JobDetails
from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.domain.proxy import BridgeEndpoint
from job_search.domain.search_query import SearchQuery


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.name = "test-portal"
    adapter.build_search_url.return_value = "http://test.url/search"
    return adapter


@pytest.fixture
def mock_proxy_pool():
    pool = MagicMock()
    pool.prepare.return_value = [BridgeEndpoint(0, "http://localhost:8080")]
    return pool


@pytest.fixture
def mock_repository():
    return MagicMock()


@pytest.fixture
def mock_filter_repository():
    repo = MagicMock()
    repo.load.return_value = MagicMock(enabled=False)
    return repo


@pytest.fixture
def mock_view():
    return MagicMock()


@pytest.fixture
def service(mock_adapter, mock_proxy_pool, mock_repository, mock_filter_repository, mock_view):
    return build_service(mock_adapter, mock_proxy_pool, mock_repository, mock_filter_repository, mock_view)


class FakeEventPublisher:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


def build_service(mock_adapter, mock_proxy_pool, mock_repository, mock_filter_repository, mock_view, publisher=None):
    reporter = DefaultSearchEventReporter(mock_adapter, publisher)
    return JobSearchService(
        adapter=mock_adapter,
        proxy_pool=mock_proxy_pool,
        filter_repository=mock_filter_repository,
        view=mock_view,
        bridge_search=BridgeSearchService(mock_adapter, mock_view, reporter),
        job_detailing=JobDetailingService(mock_adapter, mock_view, reporter),
        result_saver=SearchResultSaver(mock_repository, mock_view, reporter),
        event_reporter=reporter,
    )


@pytest.fixture
def sample_jobs():
    return [JobSummary("linkedin", f"ext-{i}", f"Job {i}") for i in range(3)]


@pytest.fixture
def sample_request():
    return JobSearchRequest(
        proxy_sources=["http://source1"],
        keywords="Python",
        location="Brasil",
        location_id=None,
        location_choice=1,
        valid_count=5,
        jobs_per_proxy=5,
        max_count=30,
        threads=4,
        timeout=10.0,
        detail_timeout=5.0,
        jobs_output="output/vagas.json",
        details_output="output/detalhadas.json",
        filters_path=None,
        details_limit=0,
        show_jobs=10,
        start=0,
        max_jobs=0,
        detail_threads=2,
    )


class TestJobSearchService:
    def test_run_success(self, service, mock_adapter, mock_view, mock_repository, mock_filter_repository, sample_request):
        mock_adapter.get_location_options.return_value = []
        mock_adapter.search_jobs.return_value = SearchResult(
            query=SearchQuery("Python", "Brasil"),
            search_url="http://url",
            response=HttpResponse(200, "http://url", {}, "<html/>"),
            jobs=[],
        )
        result = service.run(sample_request)
        assert result == 0

    def test_run_no_bridge_returns_1(self, service, mock_proxy_pool, mock_view, sample_request):
        mock_proxy_pool.prepare.return_value = []
        with pytest.raises(Exception):
            service.run(sample_request)

    def test_run_no_jobs_saves_empty(self, service, mock_adapter, mock_view, mock_repository, sample_request):
        mock_adapter.get_location_options.return_value = []
        mock_adapter.search_jobs.return_value = SearchResult(
            query=SearchQuery("Python", "Brasil"),
            search_url="http://url",
            response=HttpResponse(200, "http://url", {}, "<html/>"),
            jobs=[],
        )
        result = service.run(sample_request)
        assert result == 0
        mock_repository.save_jobs.assert_any_call("output/vagas.json", [])
        mock_repository.save_jobs.assert_any_call("output/detalhadas.json", [])

    def test_run_publishes_events(self, mock_adapter, mock_proxy_pool, mock_repository, mock_filter_repository, mock_view, sample_request):
        publisher = FakeEventPublisher()
        service = build_service(mock_adapter, mock_proxy_pool, mock_repository, mock_filter_repository, mock_view, publisher)
        mock_adapter.get_location_options.return_value = []
        mock_adapter.search_jobs.return_value = SearchResult(
            query=SearchQuery("Python", "Brasil"),
            search_url="http://url",
            response=HttpResponse(200, "http://url", {}, "<html/>"),
            jobs=[],
        )

        service.run(sample_request)

        event_names = [event.name for event in publisher.events]
        assert "job_search_started" in event_names
        assert "bridges_prepared" in event_names
        assert "search_bridge_succeeded" in event_names
        assert "job_search_no_jobs" in event_names

    def test_run_adds_modalidade_to_saved_results_and_search_data(
        self,
        mock_adapter,
        mock_proxy_pool,
        mock_repository,
        mock_filter_repository,
        mock_view,
        sample_request,
    ):
        publisher = FakeEventPublisher()
        service = build_service(mock_adapter, mock_proxy_pool, mock_repository, mock_filter_repository, mock_view, publisher)
        mock_adapter.name = "linkedin"
        request = replace(sample_request, location_id="103644278", work_type="remote", details_limit=1)
        job = JobSummary("linkedin", "e1", "Data Analyst")
        mock_adapter.search_jobs.return_value = SearchResult(
            query=SearchQuery("Python", "Brasil", "103644278", "remote"),
            search_url="http://url",
            response=HttpResponse(200, "http://url", {}, "<html/>"),
            jobs=[job],
        )
        mock_adapter.fetch_job_details.return_value = (
            JobDetails(title="Data Analyst", description="Trabalha com Python diariamente."),
            HttpResponse(200, "http://detail", {}, "<html/>"),
        )

        result = service.run(request)

        assert result == 0
        saved_summaries = mock_repository.save_jobs.call_args_list[0].args[1]
        saved_details = mock_repository.save_jobs.call_args_list[1].args[1]
        assert saved_summaries[0].to_dict()["modalidade"] == "remoto"
        assert saved_details[0].to_dict()["modalidade"] == "remoto"
        search_data_events = [event for event in publisher.events if event.name == "search_data"]
        assert search_data_events[-1].payload["data"][0]["modalidade"] == "remoto"

    def test_with_modalidade_preserves_provider_value(self, service):
        posting = JobPosting(
            summary=JobSummary(
                "linkedin",
                "e1",
                "Dev",
                provider_data={"modalidade": "presencial"},
            )
        )

        result = service._with_modalidade([posting], "hybrid")

        assert result[0] is posting
        assert result[0].to_dict()["modalidade"] == "presencial"

    def test_with_modalidade_infers_remote_from_location(self, service):
        posting = JobPosting(summary=JobSummary("glassdoor", "e1", "Dev", location="Trabalho remoto"))

        result = service._with_modalidade([posting], "normal")

        assert result[0].to_dict()["modalidade"] == "remoto"

    def test_with_modalidade_infers_hybrid_from_provider_data(self, service):
        posting = JobPosting(
            summary=JobSummary(
                "gupy",
                "e1",
                "Dev",
                provider_data={"workplaceType": "hybrid", "isRemoteWork": False},
            )
        )

        result = service._with_modalidade([posting], "normal")

        assert result[0].to_dict()["modalidade"] == "híbrido"

    def test_with_modalidade_infers_remote_from_criteria(self, service):
        posting = JobPosting(
            summary=JobSummary("gupy", "e1", "Dev"),
            details=JobDetails(criteria={"Remoto": "Sim"}),
        )

        result = service._with_modalidade([posting], "normal")

        assert result[0].to_dict()["modalidade"] == "remoto"

    @pytest.mark.parametrize(
        ("work_type", "expected"),
        [
            (None, "presencial"),
            ("normal", "presencial"),
            ("presencial", "presencial"),
            ("remote", "remoto"),
            ("remoto", "remoto"),
            ("hybrid", "híbrido"),
            ("hibrido", "híbrido"),
            ("híbrido", "híbrido"),
        ],
    )
    def test_normalize_modalidade(self, service, work_type, expected):
        assert service._normalize_modalidade(work_type) == expected

    def test_rejects_work_type_outside_linkedin(self, service, sample_request):
        request = replace(sample_request, work_type="remote")

        with pytest.raises(ValueError, match="LinkedIn"):
            service.run(request)

    def test_rejects_under_10_applicants_outside_linkedin(self, service, sample_request):
        request = replace(sample_request, under_10_applicants=True)

        with pytest.raises(ValueError, match="LinkedIn"):
            service.run(request)

    def test_prepare_bridges(self, service, mock_proxy_pool, sample_request):
        query = SearchQuery("Python", "Brasil")
        bridges = service._prepare_bridges(query, sample_request)
        mock_proxy_pool.prepare.assert_called_once()
        assert len(bridges) > 0

    def test_search_with_first_working_bridge(self, service, mock_adapter, sample_request):
        query = SearchQuery("Python", "Brasil")
        bridges = [BridgeEndpoint(0, "http://bridge:8080")]
        mock_adapter.search_jobs.return_value = SearchResult(
            query=query,
            search_url="http://search",
            response=HttpResponse(200, "http://search", {}, "result"),
            jobs=[JobSummary("linkedin", "e1", "Dev")],
        )
        result = service._search_with_first_working_bridge(query, bridges, 10.0)
        assert result is not None
        assert len(result.jobs) == 1

    def test_search_all_bridges_fail_returns_none(self, service, mock_adapter, sample_request):
        query = SearchQuery("Python", "Brasil")
        bridges = [BridgeEndpoint(0, "http://b1"), BridgeEndpoint(1, "http://b2")]
        mock_adapter.search_jobs.side_effect = Exception("fail")
        result = service._search_with_first_working_bridge(query, bridges, 10.0)
        assert result is None

    def test_filter_jobs_by_keywords_keeps_title_match(self, service):
        jobs = [
            JobPosting(summary=JobSummary("linkedin", "e1", "Python Developer")),
            JobPosting(summary=JobSummary("linkedin", "e2", "Java Developer")),
        ]

        result = service._filter_jobs_by_keywords(jobs, "python")

        assert [job.summary.external_id for job in result] == ["e1"]

    def test_filter_jobs_by_keywords_keeps_description_match(self, service):
        jobs = [
            JobPosting(
                summary=JobSummary("gupy", "e1", "Backend Developer"),
                details=JobDetails(description="Desenvolvimento de APIs com Python."),
            ),
            JobPosting(
                summary=JobSummary("gupy", "e2", "Backend Developer"),
                details=JobDetails(description="Desenvolvimento de APIs com Java."),
            ),
        ]

        result = service._filter_jobs_by_keywords(jobs, "python")

        assert [job.summary.external_id for job in result] == ["e1"]

    def test_filter_jobs_by_keywords_is_accent_insensitive(self, service):
        jobs = [JobPosting(summary=JobSummary("linkedin", "e1", "Analista de Automação"))]

        result = service._filter_jobs_by_keywords(jobs, "automacao")

        assert result == jobs

    def test_filter_jobs_by_keywords_ignores_default_placeholder(self, service):
        jobs = [JobPosting(summary=JobSummary("linkedin", "e1", "Backend Developer"))]

        result = service._filter_jobs_by_keywords(jobs, "Vagas")

        assert result == jobs

    def test_filter_jobs_no_filters(self, service, mock_filter_repository, sample_jobs):
        mock_filter_repository.load.return_value = MagicMock(enabled=False)
        jobs = [JobPosting(summary=j) for j in sample_jobs]
        result = service._filter_jobs(jobs, None)
        assert len(result) == 3

    def test_filter_jobs_with_filters(self, service, mock_filter_repository, sample_jobs):
        filter_set = MagicMock()
        filter_set.enabled = True
        filter_set.apply.return_value = [JobPosting(summary=sample_jobs[0])]
        mock_filter_repository.load.return_value = filter_set
        jobs = [JobPosting(summary=j) for j in sample_jobs]
        result = service._filter_jobs(jobs, "filters/some.json")
        assert len(result) == 1
        mock_filter_repository.load.assert_called_once_with("filters/some.json")


class TestJobSearchRequest:
    def test_fields(self):
        req = JobSearchRequest(
            proxy_sources=["src1"],
            keywords="Python",
            location="SP",
            location_id=None,
            location_choice=None,
            valid_count=10,
            jobs_per_proxy=3,
            max_count=50,
            threads=8,
            timeout=15.0,
            detail_timeout=5.0,
            jobs_output="o.json",
            details_output="d.json",
            filters_path=None,
            details_limit=0,
            show_jobs=10,
        )
        assert req.keywords == "Python"
        assert req.valid_count == 10
        assert req.jobs_per_proxy == 3

    def test_filter_by_keywords_default(self):
        req = JobSearchRequest(
            proxy_sources=[], keywords="K", location="L",
            valid_count=1, jobs_per_proxy=1, max_count=1, threads=1,
            timeout=1.0, detail_timeout=1.0, jobs_output="o", details_output="d",
            detail_threads=5, filters_path=None, details_limit=0, show_jobs=10,
            location_id=None, location_choice=None,
        )
        assert req.filter_by_keywords is False

    def test_default_max_jobs(self):
        req = JobSearchRequest(
            proxy_sources=[], keywords="K", location="L",
            valid_count=1, jobs_per_proxy=1, max_count=1, threads=1,
            timeout=1.0, detail_timeout=1.0, jobs_output="o", details_output="d",
            detail_threads=5, filters_path=None, details_limit=0, show_jobs=10,
            location_id=None, location_choice=None,
        )
        assert req.max_jobs == 0
        assert req.start == 0
        assert req.detail_threads == 5
