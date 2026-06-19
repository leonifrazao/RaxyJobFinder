from __future__ import annotations

import pytest

from job_search.domain.filtering import JobFilterSet
from job_search.domain.job_details import JobDetails
from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary


@pytest.fixture
def python_job():
    s = JobSummary("linkedin", "1", "Python Developer", "Tech Co", "SP")
    d = JobDetails(description="Desenvolvedor Python senior", criteria={"Nivel": "Senior"})
    return JobPosting(summary=s, details=d)


@pytest.fixture
def data_job():
    s = JobSummary("linkedin", "2", "Analista de Dados", "Data Inc", "RJ")
    d = JobDetails(description="Trabalhe com dados e analytics", criteria={"Nivel": "Pleno"})
    return JobPosting(summary=s, details=d)


@pytest.fixture
def java_job():
    s = JobSummary("linkedin", "3", "Java Developer", "Java Corp", "BH")
    d = JobDetails(description="Desenvolvedor Java com Spring", criteria={"Nivel": "Senior"})
    return JobPosting(summary=s, details=d)


class TestJobFilterSet:
    def test_accept_all_not_enabled(self):
        f = JobFilterSet.accept_all()
        assert not f.enabled

    def test_accept_all_passes_all_jobs(self, python_job, java_job):
        f = JobFilterSet.accept_all()
        result = f.apply([python_job, java_job])
        assert len(result) == 2

    def test_from_dict_empty_returns_accept_all(self):
        f = JobFilterSet.from_dict({})
        assert not f.enabled

    def test_from_dict_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be an object"):
            JobFilterSet.from_dict([])

    def test_contains_single_value(self, python_job, java_job):
        f = JobFilterSet.from_dict({"fields": ["title"], "contains": "Python"})
        assert f.matches(python_job)
        assert not f.matches(java_job)

    def test_contains_list_value(self, python_job, data_job, java_job):
        f = JobFilterSet.from_dict({"fields": ["title", "description"], "contains": ["Python", "dados"]})
        assert f.matches(python_job)
        assert f.matches(data_job)
        assert not f.matches(java_job)

    def test_not_contains(self, python_job, java_job):
        f = JobFilterSet.from_dict({"fields": ["title"], "not_contains": "Python"})
        assert f.matches(java_job)
        assert not f.matches(python_job)

    def test_equals(self):
        s = JobSummary("linkedin", "1", "Dev", "ACME")
        d = JobDetails(criteria={"Nivel": "Senior"})
        job = JobPosting(summary=s, details=d)
        f = JobFilterSet.from_dict({"fields": ["title"], "equals": "Dev"})
        assert f.matches(job)
        f2 = JobFilterSet.from_dict({"fields": ["title"], "equals": "dev"})
        assert f2.matches(job)

    def test_equals_case_sensitive(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["title"], "equals": "dev", "case_sensitive": True})
        assert not f.matches(job)

    def test_not_equals(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["title"], "not_equals": "dev"})
        assert not f.matches(job)

    def test_regex(self, python_job):
        f = JobFilterSet.from_dict({"fields": ["description"], "regex": r"Python\s+senior"})
        assert f.matches(python_job)

    def test_regex_case_insensitive(self, python_job):
        f = JobFilterSet.from_dict({"fields": ["description"], "regex": r"python\s+SENIOR"})
        assert f.matches(python_job)

    def test_regex_case_sensitive(self, python_job):
        f = JobFilterSet.from_dict({"fields": ["description"], "regex": r"PYTHON", "case_sensitive": True})
        assert not f.matches(python_job)

    def test_exists_true(self):
        s = JobSummary("linkedin", "1", "Dev", company="ACME")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["company"], "exists": True})
        assert f.matches(job)

    def test_exists_false(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["url"], "exists": False})
        assert f.matches(job)

    def test_in_operator(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["title"], "in": ["Dev", "Engineer", "Manager"]})
        assert f.matches(job)

    def test_in_operator_no_match(self):
        s = JobSummary("linkedin", "1", "Designer")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["title"], "in": ["Dev", "Engineer"]})
        assert not f.matches(job)

    def test_in_non_list_raises(self):
        f = JobFilterSet(expression={"fields": ["title"], "in": "not_a_list"})
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        with pytest.raises(ValueError, match="must be a list"):
            f.matches(job)

    def test_all_composite(self, python_job, java_job):
        f = JobFilterSet.from_dict({
            "all": [
                {"fields": ["criteria.Nivel"], "contains": "Senior"},
                {"fields": ["title"], "contains": "Python"},
            ]
        })
        assert f.matches(python_job)
        assert not f.matches(java_job)

    def test_any_composite(self, python_job, data_job, java_job):
        f = JobFilterSet.from_dict({
            "any": [
                {"fields": ["title"], "contains": "Python"},
                {"fields": ["title"], "contains": "Dados"},
            ]
        })
        assert f.matches(python_job)
        assert f.matches(data_job)
        assert not f.matches(java_job)

    def test_not_composite(self, python_job, java_job):
        f = JobFilterSet.from_dict({
            "not": {"fields": ["title"], "contains": "Python"}
        })
        assert f.matches(java_job)
        assert not f.matches(python_job)

    def test_nested_composite(self, python_job, data_job, java_job):
        f = JobFilterSet.from_dict({
            "all": [
                {"not": {"fields": ["title"], "contains": "Java"}},
                {"any": [
                    {"fields": ["title", "description"], "contains": "Python"},
                    {"fields": ["title", "description"], "contains": "dados"},
                ]},
            ]
        })
        assert f.matches(python_job)
        assert f.matches(data_job)
        assert not f.matches(java_job)

    def test_dot_notation_field(self, python_job):
        f = JobFilterSet.from_dict({"fields": ["criteria.Nivel"], "contains": "Senior"})
        assert f.matches(python_job)

    def test_dot_notation_missing_field(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["missing.field"], "exists": False})
        assert f.matches(job)

    def test_unknown_operator_raises(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet(expression={"fields": ["title"], "unknown_op": "val"})
        with pytest.raises(ValueError, match="requires an operator"):
            f.matches(job)

    def test_rule_without_fields_raises(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet(expression={"contains": "Python"})
        with pytest.raises(ValueError, match="requires field"):
            f.matches(job)

    def test_all_must_be_list_raises(self):
        with pytest.raises(ValueError, match="all filter must be a list"):
            JobFilterSet(expression={"all": "not_a_list"}).matches(JobPosting(JobSummary("l", "1", "T")))

    def test_any_must_be_list_raises(self):
        with pytest.raises(ValueError, match="any filter must be a list"):
            JobFilterSet(expression={"any": "not_a_list"}).matches(JobPosting(JobSummary("l", "1", "T")))

    def test_not_must_be_object_raises(self):
        with pytest.raises(ValueError, match="not filter must be an object"):
            JobFilterSet(expression={"not": "not_a_dict"}).matches(JobPosting(JobSummary("l", "1", "T")))

    def test_field_singular_alias(self, python_job):
        f = JobFilterSet.from_dict({"field": ["title"], "contains": "Python"})
        assert f.matches(python_job)

    def test_none_value_does_not_crash(self):
        s = JobSummary("linkedin", "1", "Dev")
        job = JobPosting(summary=s)
        f = JobFilterSet.from_dict({"fields": ["description"], "contains": "anything"})
        assert not f.matches(job)

    def test_description_field_matches(self, python_job, java_job):
        f = JobFilterSet.from_dict({"fields": ["description"], "contains": "Python"})
        assert f.matches(python_job)
        assert not f.matches(java_job)
