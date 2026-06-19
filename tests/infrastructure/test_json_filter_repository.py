from __future__ import annotations

import json

import pytest

from job_search.domain.filtering import JobFilterSet
from job_search.infrastructure.persistence.json_job_filter_repository import JsonJobFilterRepository


@pytest.fixture
def repo() -> JsonJobFilterRepository:
    return JsonJobFilterRepository()


class TestLoad:
    def test_none_returns_accept_all(self, repo: JsonJobFilterRepository):
        result = repo.load(None)
        assert isinstance(result, JobFilterSet)
        assert not result.enabled

    def test_empty_path_returns_accept_all(self, repo: JsonJobFilterRepository):
        result = repo.load("")
        assert isinstance(result, JobFilterSet)
        assert not result.enabled

    def test_valid_json_file(self, repo: JsonJobFilterRepository, tmp_path: pytest.TempPathFactory):
        rules = {"title": {"equals": "Engineer"}}
        path = tmp_path / "filters.json"
        path.write_text(json.dumps(rules), encoding="utf-8")

        result = repo.load(str(path))
        assert isinstance(result, JobFilterSet)
        assert result.enabled

    def test_complex_filter(self, repo: JsonJobFilterRepository, tmp_path: pytest.TempPathFactory):
        rules = {
            "all": [
                {"title": {"contains": "Senior"}},
                {"company": {"not_contains": "Recruiter"}},
            ],
        }
        path = tmp_path / "complex.json"
        path.write_text(json.dumps(rules), encoding="utf-8")

        result = repo.load(str(path))
        assert isinstance(result, JobFilterSet)
        assert result.enabled

    def test_invalid_json_raises(self, repo: JsonJobFilterRepository, tmp_path: pytest.TempPathFactory):
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            repo.load(str(path))

    def test_file_not_found_raises(self, repo: JsonJobFilterRepository):
        with pytest.raises(FileNotFoundError):
            repo.load("/nonexistent/path/filters.json")
