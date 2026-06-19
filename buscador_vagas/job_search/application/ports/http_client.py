from __future__ import annotations

from typing import Any, Protocol

from job_search.application.dto.output.http_response import HttpResponse


class HttpClient(Protocol):
    def get(self, bridge_url: str, url: str, timeout: float, *, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        ...

    def post(self, bridge_url: str, url: str, timeout: float, *, json_body: dict[str, Any] | None = None, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        ...
