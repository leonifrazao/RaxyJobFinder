from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from job_search.domain.dtos import JobDetails, JobSummary, LocationOption, SearchQuery, SearchResult, HttpResponse
from job_search.modules.glassdoor.adapter import GlassdoorJobBoardAdapter, _slugify


SAMPLE_LISTING = {
    "jobview": {
        "header": {
            "jobTitleText": "Engenheiro de Software",
            "employer": {"name": "Tech Corp", "id": "123"},
            "locationName": "São Paulo, SP",
            "ageInDays": 5,
            "seoJobLink": "https://glassdoor.com.br/vaga/eng",
            "jobLink": "/job-details/123",
            "jobResultTrackingKey": "key-abc",
            "locId": "1001",
            "locationType": "CITY",
            "easyApply": True,
            "isSponsoredJob": False,
            "payCurrency": "BRL",
            "salarySource": "Estimativa",
        },
        "job": {"listingId": 999, "description": "Vaga para engenheiro senior"},
        "overview": {"squareLogoUrl": "https://logo.com/tech.png"},
    },
}

SAMPLE_LISTING_NO_HEADER = {
    "jobview": {
        "header": {
            "jobTitleText": "Analista",
            "employer": {"name": "Data Inc"},
            "locationName": "RJ",
        },
        "job": {"listingId": 888},
    },
}

SAMPLE_DETAIL_API = {
    "data": {
        "jobview": {
            "header": {
                "jobTitleText": "Engenheiro Senior",
                "employer": {"name": "Tech Corp"},
                "locationName": "São Paulo, SP",
                "easyApply": True,
                "goc": "Engenharia",
                "salarySource": "Estimativa",
                "payCurrency": "BRL",
            },
            "job": {
                "listingId": 999,
                "description": "<p>Descricao detalhada da vaga</p>",
            },
        },
    },
}


@pytest.fixture
def adapter() -> GlassdoorJobBoardAdapter:
    return GlassdoorJobBoardAdapter(http_client=MagicMock())


@pytest.fixture
def sample_query() -> SearchQuery:
    return SearchQuery(keywords="engenheiro", location="São Paulo")


class TestSlugify:
    def test_basic(self):
        assert _slugify("Engenheiro de Software") == "engenheiro-de-software"

    def test_special_chars(self):
        assert _slugify("Dev! @# Senior") == "dev-senior"

    def test_already_slug(self):
        assert _slugify("python-dev") == "python-dev"


class TestBuildSearchUrl:
    def test_basic(self, adapter: GlassdoorJobBoardAdapter, sample_query: SearchQuery):
        url = adapter.build_search_url(sample_query)
        assert "/Vaga/engenheiro-vagas" in url
        assert "_KO" in url

    def test_with_location_id_city(self, adapter: GlassdoorJobBoardAdapter):
        q = SearchQuery(keywords="dev", location="SP", location_id="12345|C")
        url = adapter.build_search_url(q)
        assert "IC12345" in url

    def test_with_location_id_state(self, adapter: GlassdoorJobBoardAdapter):
        q = SearchQuery(keywords="dev", location="SP", location_id="67890|S")
        url = adapter.build_search_url(q)
        assert "IC67890" in url

    def test_with_location_id_country(self, adapter: GlassdoorJobBoardAdapter):
        q = SearchQuery(keywords="dev", location="Brasil", location_id="36|N")
        url = adapter.build_search_url(q)
        assert "IC" not in url

    def test_no_keywords_defaults_to_vagas(self, adapter: GlassdoorJobBoardAdapter):
        q = SearchQuery(keywords="qualquer", location="SP")
        url = adapter.build_search_url(q)
        assert "/Vaga/qualquer-vagas" in url


class TestGetLocationOptions:
    def test_parses_response(self, adapter: GlassdoorJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"locationId": "1001", "locationName": "São Paulo", "locationType": "CITY"},
            {"locationId": "1002", "locationName": "Rio de Janeiro", "locationType": "CITY"},
        ])
        mock_response.cookies = {}
        adapter.http_client.get.return_value = mock_response

        result = adapter.get_location_options("http://bridge:8080", "SP", 10.0)
        assert len(result) == 2
        assert result[0].id == "1001|CITY"
        assert result[0].name == "São Paulo"
        assert result[0].kind == "CITY"

    def test_empty_response(self, adapter: GlassdoorJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.text = "[]"
        mock_response.cookies = {}
        adapter.http_client.get.return_value = mock_response

        assert adapter.get_location_options("http://bridge:8080", "", 10.0) == []


class TestParseJobs:
    def test_parses_listing(self, adapter: GlassdoorJobBoardAdapter):
        jobs = adapter._parse_jobs([SAMPLE_LISTING])
        assert len(jobs) == 1
        job = jobs[0]
        assert job.external_id == "999"
        assert job.title == "Engenheiro de Software"
        assert job.company == "Tech Corp"
        assert job.location == "São Paulo, SP"
        assert job.listed_text == "5 dias atras"
        assert job.url == "https://glassdoor.com.br/vaga/eng"
        assert job.logo_url == "https://logo.com/tech.png"
        assert job.provider_data["jobLink"] == "/job-details/123"
        assert job.provider_data["easyApply"] is True

    def test_empty_list(self, adapter: GlassdoorJobBoardAdapter):
        assert adapter._parse_jobs([]) == []

    def test_multiple_listings(self, adapter: GlassdoorJobBoardAdapter):
        jobs = adapter._parse_jobs([SAMPLE_LISTING, SAMPLE_LISTING_NO_HEADER])
        assert len(jobs) == 2

    def test_skips_invalid(self, adapter: GlassdoorJobBoardAdapter):
        jobs = adapter._parse_jobs([{}, {"jobview": {"header": {}}}])
        assert len(jobs) == 0


class TestBuildDetailsFromSummary:
    def test_with_location(self, adapter: GlassdoorJobBoardAdapter):
        job = JobSummary(
            provider="glassdoor", external_id="999", title="Eng",
            company="Tech", location="São Paulo, SP",
            listed_text="5 dias atras", url="https://glassdoor.com/vaga",
            provider_data={"easyApply": True},
        )
        details = adapter._build_details_from_summary(job)
        assert details.title == "Eng"
        assert details.company == "Tech"
        assert details.criteria["Cidade"] == "São Paulo"
        assert details.criteria["Estado"] == "SP"
        assert details.criteria["Easy Apply"] == "Sim"

    def test_no_location(self, adapter: GlassdoorJobBoardAdapter):
        job = JobSummary(provider="glassdoor", external_id="1", title="Dev", location="")
        details = adapter._build_details_from_summary(job)
        assert details.criteria["Cidade"] == ""
        assert details.criteria["Estado"] == ""


class TestEnrichDetails:
    def test_enriches_all_fields(self, adapter: GlassdoorJobBoardAdapter):
        base = JobDetails(title="Eng", company="Tech", criteria={"Cidade": "", "Estado": ""})
        enriched = adapter._enrich_details(base, SAMPLE_DETAIL_API["data"])
        assert enriched.title == "Engenheiro Senior"
        assert enriched.company == "Tech Corp"
        assert enriched.description == "<p>Descricao detalhada da vaga</p>"
        assert enriched.criteria["Funcao"] == "Engenharia"
        assert enriched.criteria["Cidade"] == "São Paulo"
        assert enriched.criteria["Estado"] == "SP"

    def test_keeps_base_values_when_no_enrichment(self, adapter: GlassdoorJobBoardAdapter):
        base = JobDetails(title="Dev", company="Data Inc", criteria={"Cidade": "RJ"})
        enriched = adapter._enrich_details(base, {})
        assert enriched.title == "Dev"
        assert enriched.company == "Data Inc"


class TestSearchJobs:
    def test_basic_search(self, adapter: GlassdoorJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({
            "data": {
                "jobListings": {
                    "jobListings": [SAMPLE_LISTING, SAMPLE_LISTING_NO_HEADER],
                    "totalJobsCount": 2,
                    "paginationCursors": [],
                },
            },
        })
        mock_resp.cookies = {}
        adapter.http_client.get.return_value = mock_resp
        adapter.http_client.post.return_value = mock_resp

        q = SearchQuery(keywords="engenheiro", location="SP")
        result = adapter.search_jobs("http://bridge:8080", q, 10.0)
        assert len(result.jobs) == 2

    def test_non_200_raises(self, adapter: GlassdoorJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.cookies = {}
        adapter.http_client.get.return_value = mock_resp
        adapter.http_client.post.return_value = mock_resp

        q = SearchQuery(keywords="engenheiro", location="SP")
        with pytest.raises(RuntimeError, match="status HTTP"):
            adapter.search_jobs("http://bridge:8080", q, 10.0)

    def test_api_error_raises(self, adapter: GlassdoorJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({"errors": [{"message": "API limit exceeded"}]})
        mock_resp.cookies = {}
        adapter.http_client.get.return_value = mock_resp
        adapter.http_client.post.return_value = mock_resp

        q = SearchQuery(keywords="engenheiro", location="SP")
        with pytest.raises(RuntimeError, match="API limit"):
            adapter.search_jobs("http://bridge:8080", q, 10.0)


class TestFetchJobDetails:
    def test_with_enrichment(self, adapter: GlassdoorJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(SAMPLE_DETAIL_API)
        mock_resp.cookies = {}
        adapter.http_client.get.return_value = mock_resp

        job = JobSummary(
            provider="glassdoor", external_id="999", title="Eng",
            company="Tech", location="São Paulo, SP",
            provider_data={"jobLink": "/job-details/999"},
        )
        details, response = adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)
        assert details.title == "Engenheiro Senior"
        assert details.criteria["Funcao"] == "Engenharia"

    def test_fallback_when_no_enrichment(self, adapter: GlassdoorJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps({"error": "not found"})
        mock_resp.cookies = {}
        adapter.http_client.get.return_value = mock_resp

        job = JobSummary(
            provider="glassdoor", external_id="999", title="Eng",
            company="Tech", location="SP",
        )
        details, response = adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)
        assert details.title == "Eng"

    def test_non_200_returns_summary_based(self, adapter: GlassdoorJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = ""
        mock_resp.cookies = {}
        adapter.http_client.get.return_value = mock_resp

        job = JobSummary(
            provider="glassdoor", external_id="999", title="Eng",
            company="Tech", location="SP",
        )
        details, response = adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)
        assert details.title == "Eng"


class TestCookies:
    def test_update_cookies_from_response(self, adapter: GlassdoorJobBoardAdapter):
        resp = MagicMock()
        resp.cookies = {"gd_session": "abc123", "gd_prefs": "lang=pt"}
        adapter._update_cookies(resp)
        assert "gd_session=abc123" in adapter._cookie_string
        assert "gd_prefs=lang=pt" in adapter._cookie_string

    def test_update_cookies_appends_to_existing(self, adapter: GlassdoorJobBoardAdapter):
        adapter._cookie_string = "existing=cookie"
        resp = MagicMock()
        resp.cookies = {"new": "value"}
        adapter._update_cookies(resp)
        assert "existing=cookie" in adapter._cookie_string
        assert "new=value" in adapter._cookie_string

    def test_empty_cookies_does_nothing(self, adapter: GlassdoorJobBoardAdapter):
        resp = MagicMock()
        resp.cookies = {}
        adapter._update_cookies(resp)
        assert adapter._cookie_string == ""

    def test_ensure_cookies_skips_when_set(self, adapter: GlassdoorJobBoardAdapter):
        adapter._cookie_string = "existing=cookie"
        adapter._ensure_cookies("http://bridge:8080", 10.0)
        adapter.http_client.get.assert_not_called()

    def test_ensure_cookies_fetches_when_empty(self, adapter: GlassdoorJobBoardAdapter):
        mock_resp = MagicMock()
        mock_resp.cookies = {"gd": "val"}
        adapter.http_client.get.return_value = mock_resp
        adapter._ensure_cookies("http://bridge:8080", 10.0)
        adapter.http_client.get.assert_called_once()
        assert "gd=val" in adapter._cookie_string

    def test_ensure_cookies_swallows_errors(self, adapter: GlassdoorJobBoardAdapter):
        adapter.http_client.get.side_effect = RuntimeError("connection error")
        adapter._ensure_cookies("http://bridge:8080", 10.0)
        assert adapter._cookie_string == ""


class TestHeaders:
    def test_without_cookie(self, adapter: GlassdoorJobBoardAdapter):
        h = adapter._headers()
        assert "Cookie" not in h

    def test_with_cookie(self, adapter: GlassdoorJobBoardAdapter):
        adapter._cookie_string = "gd=val"
        h = adapter._headers()
        assert h["Cookie"] == "gd=val"
