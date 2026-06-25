from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("redis.asyncio")

from fastapi.testclient import TestClient

import api.main as api_main


@pytest.fixture
def client():
    return TestClient(api_main.app)


def test_health_returns_status_and_version(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}


def test_search_returns_jobs_from_runner(client, monkeypatch):
    def fake_run_search(req):
        assert req.portal == "linkedin"
        assert req.keywords == "Python"
        assert req.location == "Sao Paulo"
        assert req.details_limit == 2
        return [{"title": "Python Developer", "provider": req.portal}]

    monkeypatch.setattr(api_main, "_run_search", fake_run_search)

    response = client.post(
        "/search",
        json={
            "portal": "linkedin",
            "keywords": "Python",
            "location": "Sao Paulo",
            "details_limit": 2,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "total": 1,
        "jobs": [{"title": "Python Developer", "provider": "linkedin"}],
    }


def test_search_returns_500_when_runner_fails(client, monkeypatch):
    def fail_run_search(_req):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(api_main, "_run_search", fail_run_search)

    response = client.post("/search", json={"keywords": "Python"})

    assert response.status_code == 500
    assert response.json() == {"detail": "provider unavailable"}


def test_run_search_passes_limits_to_sdk(monkeypatch, tmp_path):
    calls = {}

    class FakeJob:
        def to_dict(self):
            return {"title": "Python Developer"}

    class FakeJobFinder:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def search(self, **kwargs):
            calls["search"] = kwargs
            return [FakeJob()]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api_main, "JobFinder", FakeJobFinder)

    req = api_main.SearchRequest(
        keywords="Python",
        max_jobs=180,
        details_limit=40,
        start=60,
        detail_threads=8,
    )

    result = api_main._run_search(req)

    assert result == [{"title": "Python Developer"}]
    assert calls["search"]["max_jobs"] == 180
    assert calls["search"]["details_limit"] == 40
    assert calls["search"]["start"] == 60
    assert calls["search"]["detail_threads"] == 8
    assert calls["init"]["keywords"] == "Python"


def test_get_output_returns_saved_json(client, monkeypatch, tmp_path):
    output_dir = tmp_path / "output" / "linkedin"
    output_dir.mkdir(parents=True)
    payload = [{"title": "Backend Engineer"}]
    (output_dir / "detalhadas.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    response = client.get("/output/linkedin?kind=detalhadas")

    assert response.status_code == 200
    assert response.json() == payload


def test_get_output_returns_404_when_file_missing(client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    response = client.get("/output/linkedin?kind=vagas")

    assert response.status_code == 404
    assert response.json()["detail"] == "Arquivo output/linkedin/vagas.json não encontrado."


def test_sse_formats_named_event_as_json_payload():
    assert api_main._sse("done", {"total": 1}) == 'event: done\ndata: {"total": 1}\n\n'


def test_openapi_includes_ui_consumed_routes(client):
    schema = client.get("/openapi.json").json()

    assert "/health" in schema["paths"]
    assert "/search" in schema["paths"]
    assert "/search/stream" in schema["paths"]
    assert "/output/{portal}" in schema["paths"]
