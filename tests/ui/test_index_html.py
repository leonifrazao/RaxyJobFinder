from __future__ import annotations

from pathlib import Path


UI_HTML = Path(__file__).resolve().parents[2] / "ui" / "index.html"


def read_ui() -> str:
    return UI_HTML.read_text(encoding="utf-8")


def test_ui_points_to_local_api():
    html = read_ui()

    assert "const API_BASE = 'http://localhost:8000'" in html


def test_ui_calls_health_before_stream_search():
    html = read_ui()

    health_index = html.index("${API_BASE}/health")
    stream_index = html.index("${API_BASE}/search/stream")

    assert health_index < stream_index
    assert "method: 'POST'" in html
    assert "headers: { 'Content-Type': 'application/json' }" in html
    assert "body: JSON.stringify(payload)" in html


def test_ui_has_required_search_controls():
    html = read_ui()

    required_ids = [
        "keywords",
        "location",
        "workType",
        "recentPeriod",
        "under10",
        "filterByKw",
        "proxyProvider",
        "validCount",
        "jobsPerProxy",
        "threads",
        "detailThreads",
        "timeout",
        "detailTimeout",
        "maxJobs",
        "startOffset",
        "detailsLimit",
        "gdCookie",
    ]

    for element_id in required_ids:
        assert f'id="{element_id}"' in html


def test_ui_payload_matches_api_search_request_fields():
    html = read_ui()

    expected_fields = [
        "portal:",
        "keywords:",
        "location:",
        "work_type:",
        "recent_period:",
        "under_10_applicants:",
        "filter_by_keywords:",
        "proxy_provider:",
        "valid_count:",
        "jobs_per_proxy:",
        "threads:",
        "detail_threads:",
        "timeout:",
        "detail_timeout:",
        "max_jobs:",
        "start:",
        "details_limit:",
        "gd_cookie:",
    ]

    for field in expected_fields:
        assert field in html


def test_ui_exposes_supported_portals():
    html = read_ui()

    assert "setPortal('linkedin'" in html
    assert "setPortal('gupy'" in html
    assert "setPortal('glassdoor'" in html
