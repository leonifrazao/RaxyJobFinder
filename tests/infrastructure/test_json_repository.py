from __future__ import annotations

import json

import pytest

from job_search.domain.job_details import JobDetails
from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.infrastructure.persistence.json_job_repository import JsonJobRepository


@pytest.fixture
def repo() -> JsonJobRepository:
    return JsonJobRepository()


class TestSaveRaw:
    def test_creates_file_with_content(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        output = str(tmp_path / "sub" / "raw.html")
        repo.save_raw(output, "<html>data</html>")
        assert (tmp_path / "sub" / "raw.html").read_text(encoding="utf-8") == "<html>data</html>"

    def test_creates_parent_directories(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        output = str(tmp_path / "a" / "b" / "c" / "file.html")
        repo.save_raw(output, "content")
        assert (tmp_path / "a" / "b" / "c" / "file.html").exists()

    def test_overwrites_existing_file(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        output = str(tmp_path / "file.html")
        repo.save_raw(output, "old")
        repo.save_raw(output, "new")
        assert (tmp_path / "file.html").read_text(encoding="utf-8") == "new"


class TestSaveJobs:
    def test_serializes_job_summary_list(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        jobs = [
            JobSummary(provider="linkedin", external_id="1", title="Eng", company="ACME"),
            JobSummary(provider="linkedin", external_id="2", title="Dev", company="ABC"),
        ]
        output = str(tmp_path / "jobs.json")
        repo.save_jobs(output, jobs)

        data = json.loads((tmp_path / "jobs.json").read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["job_id"] == "1"
        assert data[0]["title"] == "Eng"
        assert data[1]["title"] == "Dev"

    def test_serializes_job_posting_list(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        jobs = [
            JobPosting(
                summary=JobSummary(provider="gupy", external_id="10", title="Analista"),
                details=JobDetails(title="Analista Senior", description="..."),
                detail_status_code=200,
            ),
        ]
        output = str(tmp_path / "postings.json")
        repo.save_jobs(output, jobs)

        data = json.loads((tmp_path / "postings.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["job_id"] == "10"
        assert data[0]["detail_title"] == "Analista Senior"
        assert data[0]["detail_status_code"] == 200

    def test_empty_list_creates_empty_array(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        output = str(tmp_path / "empty.json")
        repo.save_jobs(output, [])
        data = json.loads((tmp_path / "empty.json").read_text(encoding="utf-8"))
        assert data == []

    def test_creates_parent_directories(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        output = str(tmp_path / "x" / "y" / "vagas.json")
        repo.save_jobs(output, [])
        assert (tmp_path / "x" / "y" / "vagas.json").exists()

    def test_omits_provider_specific_data(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        jobs = [
            JobSummary(
                provider="glassdoor", external_id="g1", title="Designer",
                provider_data={"modalidade": "remoto", "rating": 4.5, "reviews": 10},
            ),
        ]
        output = str(tmp_path / "with_extra.json")
        repo.save_jobs(output, jobs)
        data = json.loads((tmp_path / "with_extra.json").read_text(encoding="utf-8"))
        assert data[0]["modalidade"] == "remoto"
        assert data[0]["provider_data"]["rating"] == 4.5
        assert data[0]["provider_data"]["reviews"] == 10

    def test_posting_uses_shared_detail_schema(self, repo: JsonJobRepository, tmp_path: pytest.TempPathFactory):
        jobs = [
            JobPosting(
                summary=JobSummary(
                    provider="gupy",
                    external_id="10",
                    title="Analista",
                    provider_data={"modalidade": "híbrido", "workplaceType": "hybrid"},
                ),
                details=JobDetails(
                    title="Analista Senior",
                    description="...",
                    provider_data={"id": 10},
                ),
                detail_status_code=200,
            ),
        ]
        output = str(tmp_path / "postings.json")
        repo.save_jobs(output, jobs)

        data = json.loads((tmp_path / "postings.json").read_text(encoding="utf-8"))
        assert list(data[0]) == [
            "provider",
            "job_id",
            "title",
            "company",
            "location",
            "listed_at",
            "listed_text",
            "url",
            "company_url",
            "logo_url",
            "modalidade",
            "detail_title",
            "detail_company",
            "detail_company_url",
            "detail_location",
            "detail_posted_text",
            "detail_applicants_text",
            "description",
            "criteria",
            "apply_text",
            "detail_url",
            "detail_logo_url",
            "detail_status_code",
            "detail_html_size",
            "detail_bridge_index",
            "provider_data",
        ]
        assert data[0]["modalidade"] == "híbrido"
        assert data[0]["detail_title"] == "Analista Senior"
        assert data[0]["provider_data"]["workplaceType"] == "hybrid"
        assert data[0]["provider_data"]["id"] == 10
