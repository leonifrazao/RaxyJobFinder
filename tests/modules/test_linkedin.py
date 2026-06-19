from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.domain.job_details import JobDetails
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption
from job_search.domain.search_query import SearchQuery
from job_search.modules.linkedin.adapter import LinkedInJobBoardAdapter


SAMPLE_CARD_HTML = """
<div class="base-card job-search-card" data-entity-urn="urn:li:jobPosting:12345" data-reference-id="ref1" data-tracking-id="track1" data-row="1" data-column="0">
  <a class="base-card__full-link" href="/jobs/view/12345"></a>
  <div class="base-search-card__title">Engenheiro de Software</div>
  <div class="base-search-card__subtitle"><a href="/company/acme">ACME Corp</a></div>
  <div class="job-search-card__location">São Paulo, SP</div>
  <time class="job-search-card__listdate" datetime="2024-01-15">1 semana atras</time>
  <img class="artdeco-entity-image" src="https://logo.com/acme.png"/>
</div>
"""

SAMPLE_CARD_NO_LINK = """
<div class="base-card job-search-card" data-entity-urn="urn:li:jobPosting:67890">
  <div class="base-search-card__title">Dev</div>
  <div class="base-search-card__subtitle">Company</div>
  <div class="job-search-card__location">RJ</div>
</div>
"""

SAMPLE_DETAIL_HTML = """
<div>
  <div class="top-card-layout__title">Engenheiro Senior</div>
  <a class="topcard__org-name-link" href="/company/acme">ACME Corp</a>
  <div class="topcard__flavor-row"><span class="topcard__flavor--bullet">São Paulo, SP</span></div>
  <div class="posted-time-ago__text">Ha 2 semanas</div>
  <div class="num-applicants__caption">50+ candidatos</div>
  <div class="description__text"><div class="show-more-less-html__markup"><p>Vaga para engenheiro senior</p></div></div>
  <button class="top-card-layout__cta--primary">Candidate-se</button>
  <a class="topcard__link" href="/jobs/view/12345">Link</a>
  <div class="top-card-layout__card"><img class="artdeco-entity-image" src="https://logo.com/acme.png"/></div>
  <div class="description__job-criteria-item">
    <span class="description__job-criteria-subheader">Nivel</span>
    <span class="description__job-criteria-text">Senior</span>
  </div>
  <div class="description__job-criteria-item">
    <span class="description__job-criteria-subheader">Tipo</span>
    <span class="description__job-criteria-text">CLT</span>
  </div>
  <code id="decoratedJobPostingId">"decorated-123"</code>
  <code id="referenceId">"ref-abc"</code>
</div>
"""

SAMPLE_SEE_MORE_JSON = json.dumps([
    {"entityUrn": "urn:li:jobPosting:999", "title": {"text": "Dev Pleno"}},
    {"entityUrn": "urn:li:jobPosting:888", "title": {"text": "Dev Junior"}},
])


@pytest.fixture
def adapter() -> LinkedInJobBoardAdapter:
    return LinkedInJobBoardAdapter(http_client=MagicMock())


@pytest.fixture
def sample_query() -> SearchQuery:
    return SearchQuery(keywords="engenheiro", location="São Paulo", location_id="10001")


class TestBuildSearchUrl:
    def test_basic(self, adapter: LinkedInJobBoardAdapter):
        q = SearchQuery(keywords="python", location="SP")
        url = adapter.build_search_url(q)
        assert "keywords=python" in url
        assert "location=SP" in url

    def test_with_geo_id(self, adapter: LinkedInJobBoardAdapter, sample_query: SearchQuery):
        url = adapter.build_search_url(sample_query)
        assert "geoId=10001" in url
        assert "keywords=engenheiro" in url

    def test_no_location_id(self, adapter: LinkedInJobBoardAdapter):
        q = SearchQuery(keywords="dev", location="RJ")
        url = adapter.build_search_url(q)
        assert "geoId" not in url


class TestJobIdFromUrn:
    def test_valid_urn(self):
        assert LinkedInJobBoardAdapter._job_id_from_urn("urn:li:jobPosting:12345") == "12345"

    def test_empty_returns_empty(self):
        assert LinkedInJobBoardAdapter._job_id_from_urn("") == ""

    def test_no_colon_returns_empty(self):
        assert LinkedInJobBoardAdapter._job_id_from_urn("invalid") == ""


class TestHeaders:
    def test_default_headers(self):
        h = LinkedInJobBoardAdapter._headers()
        assert h["Accept"] == "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        assert "Referer" in h

    def test_custom_accept(self):
        h = LinkedInJobBoardAdapter._headers(accept="*/*")
        assert h["Accept"] == "*/*"


class TestApiHeaders:
    def test_includes_csrf(self):
        h = LinkedInJobBoardAdapter._api_headers("https://example.com")
        assert "Csrf-Token" in h
        assert h["Referer"] == "https://example.com&position=1&pageNum=0"


class TestTypeaheadUrl:
    def test_includes_query(self):
        url = LinkedInJobBoardAdapter._typeahead_url("São Paulo")
        assert "query=S%C3%A3o+Paulo" in url
        assert "typeaheadType=GEO" in url


class TestJobPostingUrl:
    def test_without_tracking_id(self):
        url = LinkedInJobBoardAdapter._job_posting_url("12345")
        assert "/12345" in url
        assert "trackingId" not in url

    def test_with_tracking_id(self):
        url = LinkedInJobBoardAdapter._job_posting_url("12345", "track-abc")
        assert "trackingId=track-abc" in url


class TestBuildSeeMoreUrl:
    def test_includes_offset(self, adapter: LinkedInJobBoardAdapter, sample_query: SearchQuery):
        url = adapter._build_see_more_url(sample_query, 60)
        assert "start=60" in url
        assert "keywords=engenheiro" in url


class TestParseJobsFromHtml:
    def test_parses_job_card(self, adapter: LinkedInJobBoardAdapter):
        jobs = adapter._parse_jobs_from_html(SAMPLE_CARD_HTML)
        assert len(jobs) == 1
        job = jobs[0]
        assert job.external_id == "12345"
        assert job.title == "Engenheiro de Software"
        assert job.company == "ACME Corp"
        assert job.location == "São Paulo, SP"
        assert job.listed_at == "2024-01-15"
        assert job.listed_text == "1 semana atras"
        assert job.url == "/jobs/view/12345"
        assert job.company_url == "/company/acme"
        assert job.logo_url == "https://logo.com/acme.png"
        assert job.provider_data["entity_urn"] == "urn:li:jobPosting:12345"

    def test_empty_html_returns_empty(self, adapter: LinkedInJobBoardAdapter):
        assert adapter._parse_jobs_from_html("") == []

    def test_no_cards_returns_empty(self, adapter: LinkedInJobBoardAdapter):
        assert adapter._parse_jobs_from_html("<html><body></body></html>") == []

    def test_skips_invalid_cards(self, adapter: LinkedInJobBoardAdapter):
        jobs = adapter._parse_jobs_from_html(SAMPLE_CARD_NO_LINK)
        assert len(jobs) == 1
        assert jobs[0].external_id == "67890"

    def test_multiple_cards(self, adapter: LinkedInJobBoardAdapter):
        html = SAMPLE_CARD_HTML + SAMPLE_CARD_NO_LINK
        jobs = adapter._parse_jobs_from_html(html)
        assert len(jobs) == 2


class TestParseJobDetailHtml:
    def test_parses_all_fields(self, adapter: LinkedInJobBoardAdapter):
        details = adapter._parse_job_detail_html(SAMPLE_DETAIL_HTML)
        assert details.title == "Engenheiro Senior"
        assert details.company == "ACME Corp"
        assert details.company_url == "/company/acme"
        assert details.location == "São Paulo, SP"
        assert details.posted_text == "Ha 2 semanas"
        assert details.applicants_text == "50+ candidatos"
        assert details.description == "Vaga para engenheiro senior"
        assert details.criteria == {"Nivel": "Senior", "Tipo": "CLT"}
        assert details.apply_text == "Candidate-se"
        assert details.url == "/jobs/view/12345"
        assert details.logo_url == "https://logo.com/acme.png"
        assert details.provider_data["decorated_job_posting_id"] == "decorated-123"
        assert details.provider_data["detail_reference_id"] == "ref-abc"

    def test_empty_html(self, adapter: LinkedInJobBoardAdapter):
        details = adapter._parse_job_detail_html("<html></html>")
        assert details.title == ""
        assert details.criteria == {}

    def test_minimal_detail(self, adapter: LinkedInJobBoardAdapter):
        html = "<div><div class='top-card-layout__title'>Dev</div></div>"
        details = adapter._parse_job_detail_html(html)
        assert details.title == "Dev"


class TestParseJobsFromApi:
    def test_json_array_returns_empty(self, adapter: LinkedInJobBoardAdapter):
        jobs = adapter._parse_jobs_from_api("[]")
        assert jobs == []

    def test_json_with_included_list(self, adapter: LinkedInJobBoardAdapter):
        data = json.dumps({"included": json.loads(SAMPLE_SEE_MORE_JSON)})
        jobs = adapter._parse_jobs_from_api(data)
        assert jobs == []

    def test_plain_html_falls_back(self, adapter: LinkedInJobBoardAdapter):
        jobs = adapter._parse_jobs_from_api(SAMPLE_CARD_HTML)
        assert len(jobs) == 1

    def test_empty_string_returns_empty(self, adapter: LinkedInJobBoardAdapter):
        assert adapter._parse_jobs_from_api("") == []

    def test_invalid_json_falls_back_to_html(self, adapter: LinkedInJobBoardAdapter):
        jobs = adapter._parse_jobs_from_api("not json")
        assert jobs == []


class TestGetLocationOptions:
    def test_parses_typeahead_response(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"id": 10001, "displayName": "São Paulo", "type": "CITY"},
            {"id": 10002, "displayName": "Rio de Janeiro", "type": "CITY"},
        ])
        adapter.http_client.get.return_value = mock_response

        result = adapter.get_location_options("http://bridge:8080", "São Paulo", 10.0)
        assert len(result) == 2
        assert result[0].id == "10001"
        assert result[0].name == "São Paulo"
        assert result[0].kind == "CITY"

    def test_empty_response(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.text = "[]"
        adapter.http_client.get.return_value = mock_response

        result = adapter.get_location_options("http://bridge:8080", "", 10.0)
        assert result == []

    def test_invalid_json_raises(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.text = "not json"
        adapter.http_client.get.return_value = mock_response

        with pytest.raises(RuntimeError, match="JSON invalido"):
            adapter.get_location_options("http://bridge:8080", "x", 10.0)

    def test_non_list_data_raises(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.text = json.dumps({"key": "value"})
        adapter.http_client.get.return_value = mock_response

        with pytest.raises(RuntimeError, match="formato inesperado"):
            adapter.get_location_options("http://bridge:8080", "x", 10.0)


class TestSearchJobs:
    def test_parses_html_response(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_CARD_HTML
        adapter.http_client.get.return_value = mock_response

        q = SearchQuery(keywords="engenheiro", location="SP")
        result = adapter.search_jobs("http://bridge:8080", q, 10.0)
        assert len(result.jobs) == 1
        assert result.jobs[0].external_id == "12345"

    def test_non_200_raises(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.status_code = 500
        adapter.http_client.get.return_value = mock_response

        q = SearchQuery(keywords="engenheiro", location="SP")
        with pytest.raises(RuntimeError, match="status HTTP"):
            adapter.search_jobs("http://bridge:8080", q, 10.0)

    def test_pagination_when_max_jobs_exceeds(self, adapter: LinkedInJobBoardAdapter):
        api_card = """
        <div class="base-card job-search-card" data-entity-urn="urn:li:jobPosting:99999">
          <a class="base-card__full-link" href="/jobs/view/99999"></a>
          <div class="base-search-card__title">Dev Pleno</div>
          <div class="base-search-card__subtitle">Company</div>
          <div class="job-search-card__location">SP</div>
        </div>
        """
        mock_search = MagicMock()
        mock_search.status_code = 200
        mock_search.text = SAMPLE_CARD_HTML
        adapter.http_client.get.return_value = mock_search

        mock_api = MagicMock()
        mock_api.status_code = 200
        mock_api.text = api_card * 2
        adapter.http_client.get.side_effect = [mock_search, mock_api, mock_api]

        q = SearchQuery(keywords="engenheiro", location="SP")
        result = adapter.search_jobs("http://bridge:8080", q, 10.0, max_jobs=5)
        assert len(result.jobs) == 3


class TestFetchJobDetails:
    def test_fetches_and_parses(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_DETAIL_HTML
        adapter.http_client.get.return_value = mock_response

        job = JobSummary(provider="linkedin", external_id="12345", title="Eng", provider_data={"tracking_id": "track1", "row": "1"})
        details, response = adapter.fetch_job_details("http://bridge:8080", job, "https://linkedin.com/search", 10.0)
        assert details.title == "Engenheiro Senior"
        assert response.status_code == 200

    def test_missing_external_id_raises(self, adapter: LinkedInJobBoardAdapter):
        job = JobSummary(provider="linkedin", external_id="", title="Eng")
        with pytest.raises(RuntimeError, match="job_id ausente"):
            adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)

    def test_non_200_raises(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.status_code = 404
        adapter.http_client.get.return_value = mock_response

        job = JobSummary(provider="linkedin", external_id="12345", title="Eng")
        with pytest.raises(RuntimeError, match="status HTTP"):
            adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)

    def test_empty_text_raises(self, adapter: LinkedInJobBoardAdapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        adapter.http_client.get.return_value = mock_response

        job = JobSummary(provider="linkedin", external_id="12345", title="Eng")
        with pytest.raises(RuntimeError, match="vazio"):
            adapter.fetch_job_details("http://bridge:8080", job, "", 10.0)


class TestCleanText:
    def test_none_returns_empty(self):
        assert LinkedInJobBoardAdapter._clean_text(None) == ""

    def test_empty_returns_empty(self):
        assert LinkedInJobBoardAdapter._clean_text("") == ""

    def test_normalizes_spaces(self):
        assert LinkedInJobBoardAdapter._clean_text("  texto   com  espacos  ") == "texto com espacos"
