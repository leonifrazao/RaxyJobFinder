from __future__ import annotations

import pytest

from job_search.domain.dtos import BridgeEndpoint, HttpResponse, JobDetails, JobSummary
from job_search.domain.entities import JobDetailingSession


@pytest.fixture
def bridges():
    return [BridgeEndpoint(i, f"http://bridge{i}") for i in range(3)]


@pytest.fixture
def jobs():
    return [JobSummary("linkedin", f"ext-{i}", f"Job {i}") for i in range(10)]


class TestJobDetailingSession:
    def test_requires_at_least_one_bridge(self):
        with pytest.raises(ValueError, match="at least one bridge"):
            JobDetailingSession(jobs=[], bridges=[], jobs_per_proxy=5)

    def test_jobs_per_proxy_min_one(self, bridges):
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=0)
        assert s.jobs_per_proxy == 1

        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=-5)
        assert s.jobs_per_proxy == 1

    def test_jobs_to_detail_all_when_limit_zero(self, jobs, bridges):
        s = JobDetailingSession(jobs=jobs, bridges=bridges, jobs_per_proxy=5, detail_limit=0)
        assert s.jobs_to_detail == jobs

    def test_jobs_to_detail_respects_limit(self, jobs, bridges):
        s = JobDetailingSession(jobs=jobs, bridges=bridges, jobs_per_proxy=5, detail_limit=3)
        assert s.jobs_to_detail == jobs[:3]
        assert len(s.jobs_to_detail) == 3

    def test_untouched_jobs_empty_when_limit_zero(self, jobs, bridges):
        s = JobDetailingSession(jobs=jobs, bridges=bridges, jobs_per_proxy=5, detail_limit=0)
        assert s.untouched_jobs == []

    def test_untouched_jobs_returns_remaining(self, jobs, bridges):
        s = JobDetailingSession(jobs=jobs, bridges=bridges, jobs_per_proxy=5, detail_limit=3)
        assert s.untouched_jobs == jobs[3:]

    def test_bridge_candidates_rotates_by_jobs_per_proxy(self, bridges):
        jobs = [JobSummary("linkedin", f"e{i}", f"J{i}") for i in range(4)]
        s = JobDetailingSession(jobs=jobs, bridges=bridges, jobs_per_proxy=2)
        # job 0 -> bridge 0 (0 // 2 = 0 % 3 = 0)
        cand0 = s.bridge_candidates_for(0)
        assert cand0[0] == bridges[0]
        # job 2 -> bridge 1 (2 // 2 = 1 % 3 = 1)
        cand2 = s.bridge_candidates_for(2)
        assert cand2[0] == bridges[1]

    def test_bridge_candidates_fallback_when_all_blocked(self, bridges):
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=5)
        for b in bridges:
            s.mark_bridge_failed(b)
        # all bridges blocked -> returns the ordered list anyway
        candidates = s.bridge_candidates_for(0)
        assert len(candidates) == 3

    def test_bridge_candidates_skips_blocked(self, bridges):
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=5)
        s.mark_bridge_failed(bridges[1])
        candidates = s.bridge_candidates_for(0)
        assert bridges[0] in candidates
        assert bridges[1] not in candidates
        assert bridges[2] in candidates

    def test_bridge_candidates_negative_offset_raises(self, bridges):
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=5)
        with pytest.raises(ValueError, match="non-negative"):
            s.bridge_candidates_for(-1)

    def test_mark_bridge_failed(self, bridges):
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=5)
        s.mark_bridge_failed(bridges[0])
        assert 0 in s.blocked_bridge_indexes

    def test_missing_external_id(self, bridges):
        job = JobSummary("linkedin", "", "No ID")
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=5)
        p = s.missing_external_id(job)
        assert p.summary is job
        assert p.detail_error == "job_id ausente"
        assert p.details is None

    def test_successful_detail(self, bridges):
        job = JobSummary("linkedin", "e1", "Dev")
        details = JobDetails(title="Dev Senior")
        response = HttpResponse(200, "http://url", {}, "some html body")
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=5)
        p = s.successful_detail(job, details, response, bridges[0])
        assert p.summary is job
        assert p.details is details
        assert p.detail_status_code == 200
        assert p.detail_html_size == len("some html body")
        assert p.detail_bridge_index == 0
        assert p.detail_error == ""

    def test_failed_detail(self, bridges):
        job = JobSummary("linkedin", "e1", "Dev")
        s = JobDetailingSession(jobs=[], bridges=bridges, jobs_per_proxy=5)
        p = s.failed_detail(job, "connection refused")
        assert p.summary is job
        assert p.details is None
        assert p.detail_error == "connection refused"

    def test_unprocessed_postings(self, jobs, bridges):
        s = JobDetailingSession(jobs=jobs, bridges=bridges, jobs_per_proxy=5, detail_limit=3)
        unprocessed = s.unprocessed_postings()
        assert len(unprocessed) == 7
        assert all(p.summary.external_id.startswith("ext-") for p in unprocessed)
        assert all(p.details is None for p in unprocessed)

    def test_unprocessed_postings_empty_when_no_limit(self, jobs, bridges):
        s = JobDetailingSession(jobs=jobs, bridges=bridges, jobs_per_proxy=5, detail_limit=0)
        assert s.unprocessed_postings() == []
