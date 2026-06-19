from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.domain.job_details import JobDetails
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption
from job_search.domain.search_query import SearchQuery
from job_search.providers.job_boards.gupy.adapter import GupyJobBoardAdapter


SAMPLE_JOB_API = {
    "id": 123,
    "name": "Engenheiro de Software",
    "careerPageName": "Tech Corp",
    "city": "São Paulo",
    "state": "SP",
    "country": "Brasil",
    "publishedDate": "2024-01-15T10:00:00.000Z",
    "jobUrl": "https://gupy.io/jobs/123",
    "careerPageUrl": "https://tech.careers.com",
    "careerPageLogo": "https://logo.com/tech.png",
    "workplaceType": "remote",
    "type": "vacancy_type_effective",
    "isRemoteWork": True,
    "disabilities": False,
    "badges": {"highlighted": True},
    "companyId": 456,
    "careerPageId": 789,
    "applicationDeadline": "2024-02-15T23:59:59.000Z",
}

SAMPLE_JOB_DETAIL_API = {
    "id": 123,
    "name": "Engenheiro de Software Senior",
    "careerPageName": "Tech Corp",
    "city": "São Paulo",
    "state": "SP",
    "publishedDate": "2024-01-15T10:00:00.000Z",
    "jobUrl": "https://gupy.io/jobs/123",
    "careerPageUrl": "https://tech.careers.com",
    "description": "<p>Vaga para engenheiro senior com &amp; responsabilidades</p>",
    "workplaceType": "remote",
    "type": "vacancy_type_effective",
    "isRemoteWork": True,
    "disabilities": True,
    "badges": {"highlighted": True},
    "companyId": 456,
    "applicationDeadline": "2024-02-15T23:59:59.000Z",
    "careerPageLogo": "https://logo.com/tech.png",
}

IBGE_ESTADOS = json.dumps([
    {"id": 35, "nome": "São Paulo", "sigla": "SP"},
    {"id": 33, "nome": "Rio de Janeiro", "sigla": "RJ"},
])

IBGE_MUNICIPIOS_SP = json.dumps([
    {"id": 3550308, "nome": "São Paulo"},
    {"id": 3548708, "nome": "Campinas"},
])


@pytest.fixture
def adapter() -> GupyJobBoardAdapter:
    return GupyJobBoardAdapter(http_client=MagicMock())


@pytest.fixture
def sample_query() -> SearchQuery:
    return SearchQuery(keywords="engenheiro", location="São Paulo")


class TestBuildSearchUrl:
    def test_basic(self, adapter: GupyJobBoardAdapter, sample_query: SearchQuery):
        url = adapter.build_search_url(sample_query)
        assert "jobName=engenheiro" in url

    def test_without_keywords(self, adapter: GupyJobBoardAdapter):
        q = SearchQuery(keywords="dev", location="SP")
        url = adapter.build_search_url(q)
        assert "jobName=dev" in url

    def test_with_location_id(self, adapter: GupyJobBoardAdapter):
        q = SearchQuery(keywords="dev", location="SP", location_id="São Paulo|Campinas")
        url = adapter.build_search_url(q)
        assert "state=S%C3%A3o+Paulo" in url
        assert "city=Campinas" in url

    def test_brazil_location_id_omits_state_city(self, adapter: GupyJobBoardAdapter):
        q = SearchQuery(keywords="dev", location="Brasil", location_id="BR")
        url = adapter.build_search_url(q)
        assert "state" not in url
        assert "city" not in url


class TestParseLocation:
    def test_with_location_id(self):
        q = SearchQuery(keywords="dev", location="SP", location_id="São Paulo|Campinas")
        state, city = GupyJobBoardAdapter._parse_location(q)
        assert state == "São Paulo"
        assert city == "Campinas"

    def test_brazil_id(self):
        q = SearchQuery(keywords="dev", location="Brasil", location_id="BR")
        state, city = GupyJobBoardAdapter._parse_location(q)
        assert state == ""
        assert city == ""

    def test_no_location_id_falls_back_to_location(self):
        q = SearchQuery(keywords="dev", location="SP")
        state, city = GupyJobBoardAdapter._parse_location(q)
        assert state == "SP"
        assert city == ""

    def test_brazil_location_returns_empty(self):
        q = SearchQuery(keywords="dev", location="Brasil (todas as localidades)")
        state, city = GupyJobBoardAdapter._parse_location(q)
        assert state == ""
        assert city == ""


class TestFormatLocation:
    def test_both_present(self):
        assert GupyJobBoardAdapter._format_location("São Paulo", "SP") == "São Paulo, SP"

    def test_only_city(self):
        assert GupyJobBoardAdapter._format_location("São Paulo", "") == "São Paulo"

    def test_only_state(self):
        assert GupyJobBoardAdapter._format_location("", "SP") == "SP"

    def test_both_empty(self):
        assert GupyJobBoardAdapter._format_location("", "") == ""


class TestTypeLabel:
    def test_known_types(self):
        assert GupyJobBoardAdapter._type_label("vacancy_type_effective") == "Efetivo/CLT"
        assert GupyJobBoardAdapter._type_label("vacancy_type_temporary") == "Temporário"
        assert GupyJobBoardAdapter._type_label("vacancy_type_internship") == "Estágio"
        assert GupyJobBoardAdapter._type_label("vacancy_type_trainee") == "Trainee"
        assert GupyJobBoardAdapter._type_label("vacancy_type_young_apprentice") == "Jovem Aprendiz"

    def test_unknown_type_passthrough(self):
        assert GupyJobBoardAdapter._type_label("custom_type") == "custom_type"


class TestWorkplaceLabel:
    def test_known_labels(self):
        assert GupyJobBoardAdapter._workplace_label("remote") == "Remoto"
        assert GupyJobBoardAdapter._workplace_label("hybrid") == "Híbrido"
        assert GupyJobBoardAdapter._workplace_label("on-site") == "Presencial"

    def test_unknown_passthrough(self):
        assert GupyJobBoardAdapter._workplace_label("other") == "other"


class TestParseJobs:
    def test_parses_job(self, adapter: GupyJobBoardAdapter):
        jobs = adapter._parse_jobs([SAMPLE_JOB_API])
        assert len(jobs) == 1
        job = jobs[0]
        assert job.external_id == "123"
        assert job.title == "Engenheiro de Software"
        assert job.company == "Tech Corp"
        assert job.location == "São Paulo, SP"
        assert job.listed_at == "2024-01-15T10:00:00.000Z"
        assert job.url == "https://gupy.io/jobs/123"

    def test_empty_list(self, adapter: GupyJobBoardAdapter):
        assert adapter._parse_jobs([]) == []

    def test_skips_invalid_items(self, adapter: GupyJobBoardAdapter):
        jobs = adapter._parse_jobs([{}, {"id": None, "name": ""}])
        assert len(jobs) == 0


class TestParseJobDetail:
    def test_parses_all_fields(self, adapter: GupyJobBoardAdapter):
        details = adapter._parse_job_detail(SAMPLE_JOB_DETAIL_API)
        assert details.title == "Engenheiro de Software Senior"
        assert details.company == "Tech Corp"
        assert details.location == "São Paulo, SP"
        assert "Vaga para engenheiro senior" in details.description
        assert "&amp;" not in details.description
        assert details.criteria["Tipo"] == "Efetivo/CLT"
        assert details.criteria["Cidade"] == "São Paulo"
        assert details.criteria["Estado"] == "SP"
        assert details.criteria["Trabalho"] == "Remoto"
        assert details.criteria["Remoto"] == "Sim"
        assert details.criteria["PCD"] == "Sim"
        assert details.criteria["Prazo"] == "2024-02-15T23:59:59.000Z"

    def test_empty_dict(self, adapter: GupyJobBoardAdapter):
        details = adapter._parse_job_detail({})
        assert details.title == ""
        assert details.criteria["Tipo"] == ""


class TestGetLocationOptions:
    def test_finds_state_and_returns_cities(self, adapter: GupyJobBoardAdapter):
        estados_resp = MagicMock()
        estados_resp.text = IBGE_ESTADOS
        cidades_resp = MagicMock()
        cidades_resp.text = IBGE_MUNICIPIOS_SP

        adapter.http_client.get.side_effect = [estados_resp, cidades_resp]

        result = adapter.get_location_options("http://bridge:8080", "SP", 10.0)
        assert len(result) == 2
        assert result[0].id == "São Paulo|São Paulo"
        assert result[0].name == "São Paulo"
        assert result[0].kind == "city"

    def test_no_state_match_returns_brasil(self, adapter: GupyJobBoardAdapter):
        estados_resp = MagicMock()
        estados_resp.text = IBGE_ESTADOS
        adapter.http_client.get.return_value = estados_resp

        result = adapter.get_location_options("http://bridge:8080", "ZZ", 10.0)
        assert len(result) == 1
        assert result[0].id == "BR"
        assert result[0].name == "Brasil (todas as localidades)"

    def test_match_by_name_substring(self, adapter: GupyJobBoardAdapter):
        estados_resp = MagicMock()
        estados_resp.text = IBGE_ESTADOS
        cidades_resp = MagicMock()
        cidades_resp.text = "[]"
        adapter.http_client.get.side_effect = [estados_resp, cidades_resp]

        result = adapter.get_location_options("http://bridge:8080", "Janeiro", 10.0)
        assert len(result) == 0


class TestSearchJobs:
    def test_basic_search(self, adapter: GupyJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({
            "data": [SAMPLE_JOB_API],
            "pagination": {"total": 1, "limit": 100, "offset": 0},
        })
        adapter.http_client.get.return_value = mock_resp

        q = SearchQuery(keywords="engenheiro", location="SP")
        result = adapter.search_jobs("http://bridge:8080", q, 10.0)
        assert len(result.jobs) == 1
        assert result.jobs[0].external_id == "123"

    def test_non_200_raises(self, adapter: GupyJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        adapter.http_client.get.return_value = mock_resp

        q = SearchQuery(keywords="engenheiro", location="SP")
        with pytest.raises(RuntimeError, match="status HTTP"):
            adapter.search_jobs("http://bridge:8080", q, 10.0)

    def test_pagination(self, adapter: GupyJobBoardAdapter):
        page1 = MagicMock()
        page1.status_code = 200
        page1.text = json.dumps({
            "data": [SAMPLE_JOB_API],
            "pagination": {"total": 150, "limit": 100, "offset": 0},
        })
        page2 = MagicMock()
        page2.status_code = 200
        page2.text = json.dumps({
            "data": [SAMPLE_JOB_API],
            "pagination": {"total": 150, "limit": 100, "offset": 100},
        })
        adapter.http_client.get.side_effect = [page1, page2]

        q = SearchQuery(keywords="engenheiro", location="SP")
        result = adapter.search_jobs("http://bridge:8080", q, 10.0)
        assert len(result.jobs) == 2

    def test_empty_response(self, adapter: GupyJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({"data": [], "pagination": {"total": 0}})
        adapter.http_client.get.return_value = mock_resp

        q = SearchQuery(keywords="engenheiro", location="SP")
        result = adapter.search_jobs("http://bridge:8080", q, 10.0)
        assert result.jobs == []


class TestFetchJobDetails:
    def test_fetches_and_parses(self, adapter: GupyJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(SAMPLE_JOB_DETAIL_API)
        adapter.http_client.get.return_value = mock_resp

        job = JobSummary(provider="gupy", external_id="123", title="Eng")
        details, response = adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)
        assert details.title == "Engenheiro de Software Senior"
        assert response.status_code == 200

    def test_missing_external_id_raises(self, adapter: GupyJobBoardAdapter):
        job = JobSummary(provider="gupy", external_id="", title="Eng")
        with pytest.raises(RuntimeError, match="job_id ausente"):
            adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)

    def test_non_200_raises(self, adapter: GupyJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        adapter.http_client.get.return_value = mock_resp

        job = JobSummary(provider="gupy", external_id="999", title="Eng")
        with pytest.raises(RuntimeError, match="status HTTP"):
            adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)
