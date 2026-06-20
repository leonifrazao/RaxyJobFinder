from __future__ import annotations

import pytest

from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.domain.job_details import JobDetails
from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption
from job_search.domain.proxy import BridgeEndpoint
from job_search.domain.search_query import SearchQuery
from job_search.domain.text import clean_text as _clean


class TestClean:
    def test_none_returns_empty(self):
        assert _clean(None) == ""

    def test_empty_returns_empty(self):
        assert _clean("") == ""

    def test_normalizes_whitespace(self):
        assert _clean("  Python   Developer  ") == "Python Developer"

    def test_strips_surrounding_spaces(self):
        assert _clean("  hello  ") == "hello"


class TestBridgeEndpoint:
    def test_valid(self):
        b = BridgeEndpoint(0, "http://localhost:8080")
        assert b.index == 0
        assert b.url == "http://localhost:8080"

    def test_negative_index_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            BridgeEndpoint(-1, "http://localhost")

    def test_empty_url_raises(self):
        with pytest.raises(ValueError, match="url is required"):
            BridgeEndpoint(0, "")


class TestHttpResponse:
    def test_default_cookies_is_empty(self):
        r = HttpResponse(200, "http://example.com", {"content-type": "text/html"}, "<html/>")
        assert r.cookies == {}

    def test_with_all_fields(self):
        r = HttpResponse(200, "url", {"h": "v"}, "body", {"session": "abc"})
        assert r.status_code == 200
        assert r.headers["h"] == "v"
        assert r.cookies["session"] == "abc"


class TestLocationOption:
    def test_valid(self):
        loc = LocationOption("106057199", "Brasil", "GEO", "linkedin", {"key": "val"})
        assert loc.id == "106057199"
        assert loc.name == "Brasil"
        assert loc.kind == "GEO"
        assert loc.raw["key"] == "val"

    def test_empty_id_raises(self):
        with pytest.raises(ValueError, match="id is required"):
            LocationOption("", "Nome")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name is required"):
            LocationOption("123", "")

    def test_defaults(self):
        loc = LocationOption("123", "Nome")
        assert loc.kind == ""
        assert loc.provider == ""
        assert loc.raw == {}


class TestSearchQuery:
    def test_valid(self):
        q = SearchQuery("Python", "Brasil", "106057199")
        assert q.keywords == "Python"
        assert q.location == "Brasil"
        assert q.location_id == "106057199"

    def test_empty_keywords_raises(self):
        with pytest.raises(ValueError, match="keywords are required"):
            SearchQuery("", "Brasil")

    def test_whitespace_keywords_raises(self):
        with pytest.raises(ValueError, match="keywords are required"):
            SearchQuery("   ", "Brasil")

    def test_location_id_defaults_to_none(self):
        q = SearchQuery("Python", "Brasil")
        assert q.location_id is None

    def test_with_location_returns_new_query(self):
        q = SearchQuery("Python", "Brasil", work_type="remote", under_10_applicants=True)
        loc = LocationOption("106057199", "Brasil")
        q2 = q.with_location(loc)
        assert q2 is not q
        assert q2.location == "Brasil"
        assert q2.location_id == "106057199"
        assert q2.keywords == "Python"
        assert q2.work_type == "remote"
        assert q2.under_10_applicants is True


class TestJobSummary:
    def test_minimal(self):
        j = JobSummary("linkedin", "ext-1", "Engenheiro")
        assert j.provider == "linkedin"
        assert j.external_id == "ext-1"
        assert j.title == "Engenheiro"
        assert j.company == ""
        assert j.provider_data == {}

    def test_title_empty_with_url_is_valid(self):
        j = JobSummary("linkedin", "ext-2", "", url="http://jobs")
        assert j.title == ""
        assert j.url == "http://jobs"

    def test_empty_title_and_url_raises(self):
        with pytest.raises(ValueError, match="title or url"):
            JobSummary("linkedin", "ext-3", "")

    def test_to_dict(self):
        j = JobSummary(
            "linkedin", "ext-4", "Dev", "Company", "SP",
            "2024-01-01", "1 day ago", "http://url", "http://company",
            "http://logo", {"custom": "val"},
        )
        d = j.to_dict()
        assert d["provider"] == "linkedin"
        assert d["job_id"] == "ext-4"
        assert d["title"] == "Dev"
        assert d["company"] == "Company"
        assert d["location"] == "SP"
        assert d["listed_at"] == 1704067200
        assert d["listed_text"] == "1 day ago"
        assert d["url"] == "http://url"
        assert d["company_url"] == "http://company"
        assert d["logo_url"] == "http://logo"
        assert d["custom"] == "val"

    def test_to_dict_includes_provider_data(self):
        j = JobSummary("linkedin", "ext-5", "Dev", provider_data={"extra": "data"})
        d = j.to_dict()
        assert d["extra"] == "data"

    def test_to_dict_converts_iso_datetime_to_unix_timestamp(self):
        j = JobSummary("gupy", "ext-6", "Dev", listed_at="2024-01-15T10:00:00.000Z")

        d = j.to_dict()

        assert d["listed_at"] == 1705312800

    def test_to_dict_preserves_unknown_date_text(self):
        j = JobSummary("glassdoor", "ext-7", "Dev", listed_at="ontem")

        d = j.to_dict()

        assert d["listed_at"] == "ontem"


class TestJobDetails:
    def test_defaults(self):
        d = JobDetails()
        assert d.title == ""
        assert d.criteria == {}
        assert d.provider_data == {}

    def test_to_dict(self):
        d = JobDetails(
            title="Dev Senior", company="ACME", company_url="http://acme",
            location="SP", posted_text="Hoje", applicants_text="10 candidatos",
            description="Vaga top", criteria={"Nivel": "Senior"},
            apply_text="Candidate-se", url="http://detail", logo_url="http://logo",
            provider_data={"extra": "info"},
        )
        out = d.to_dict()
        assert out["detail_title"] == "Dev Senior"
        assert out["detail_company"] == "ACME"
        assert out["detail_company_url"] == "http://acme"
        assert out["detail_location"] == "SP"
        assert out["detail_posted_text"] == "Hoje"
        assert out["detail_applicants_text"] == "10 candidatos"
        assert out["description"] == "Vaga top"
        assert out["criteria"] == {"Nivel": "Senior"}
        assert out["apply_text"] == "Candidate-se"
        assert out["detail_url"] == "http://detail"
        assert out["detail_logo_url"] == "http://logo"
        assert out["extra"] == "info"

    def test_to_dict_without_provider_data(self):
        d = JobDetails(title="Dev")
        out = d.to_dict()
        assert "detail_title" in out
        assert out["detail_title"] == "Dev"


class TestJobPosting:
    def test_minimal(self):
        j = JobSummary("linkedin", "ext-1", "Dev")
        p = JobPosting(summary=j)
        assert p.summary is j
        assert p.details is None
        assert p.detail_status_code is None
        assert p.detail_html_size == 0
        assert p.detail_bridge_index is None
        assert p.detail_error == ""

    def test_to_dict_with_details(self):
        j = JobSummary("linkedin", "ext-1", "Dev")
        d = JobDetails(title="Dev Senior")
        p = JobPosting(summary=j, details=d, detail_status_code=200, detail_html_size=500, detail_bridge_index=0)
        out = p.to_dict()
        assert out["provider"] == "linkedin"
        assert out["title"] == "Dev"
        assert out["detail_title"] == "Dev Senior"
        assert out["detail_status_code"] == 200
        assert out["detail_html_size"] == 500
        assert out["detail_bridge_index"] == 0

    def test_to_dict_with_error(self):
        j = JobSummary("linkedin", "ext-1", "Dev")
        p = JobPosting(summary=j, detail_error="timeout")
        out = p.to_dict()
        assert out["detail_error"] == "timeout"

    def test_to_dict_skips_optional_fields_when_falsy(self):
        j = JobSummary("linkedin", "ext-1", "Dev")
        p = JobPosting(summary=j)
        out = p.to_dict()
        assert "detail_status_code" not in out
        assert "detail_html_size" not in out
        assert "detail_bridge_index" not in out
        assert "detail_error" not in out


class TestSearchResult:
    def test_fields(self):
        q = SearchQuery("Python", "Brasil")
        resp = HttpResponse(200, "http://url", {}, "html")
        jobs = [JobSummary("linkedin", "e1", "Dev")]
        sr = SearchResult(q, "http://search", resp, jobs)
        assert sr.query is q
        assert sr.search_url == "http://search"
        assert sr.response is resp
        assert sr.jobs is jobs
