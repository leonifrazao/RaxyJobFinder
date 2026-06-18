from __future__ import annotations

from typing import Any

from botasaurus.request import Request, request as botasaurus_request

from job_search.domain.dtos import HttpResponse


class BotasaurusHttpClient:
    def _to_cookies(self, jar: Any) -> dict[str, str]:
        return {c.name: c.value for c in jar} if jar else {}

    def get(self, bridge_url: str, url: str, timeout: float, *, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        @botasaurus_request(
            proxy=bridge_url,
            output=None,
            max_retry=max_retry,
        )
        def request_task(request: Request, data):
            response = request.get(
                data["url"],
                headers=data["headers"],
                timeout=data["timeout"],
                allow_redirects=True,
            )
            return {
                "status_code": response.status_code,
                "url": response.url,
                "headers": dict(response.headers),
                "text": response.text,
                "cookies": dict(response.cookies) if hasattr(response, "cookies") else {},
            }

        result = request_task({"url": url, "timeout": timeout, "headers": headers or {}})
        if result is None:
            raise RuntimeError("request retornou sem resposta")
        return HttpResponse(
            status_code=result.get("status_code"),
            url=result.get("url") or url,
            headers=result.get("headers") or {},
            text=result.get("text") or "",
            cookies=result.get("cookies") or {},
        )

    def post(self, bridge_url: str, url: str, timeout: float, *, json_body: dict[str, Any] | None = None, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        @botasaurus_request(
            proxy=bridge_url,
            output=None,
            max_retry=max_retry,
        )
        def request_task(request: Request, data):
            req_headers = dict(data["headers"])
            body = data.get("json_body")
            if body is not None:
                req_headers.setdefault("Content-Type", "application/json")
                import json as _json
                body_str = _json.dumps(body)
            else:
                body_str = None
            response = request.post(
                data["url"],
                data=body_str,
                headers=req_headers,
                timeout=data["timeout"],
                allow_redirects=True,
            )
            return {
                "status_code": response.status_code,
                "url": response.url,
                "headers": dict(response.headers),
                "text": response.text,
                "cookies": dict(response.cookies) if hasattr(response, "cookies") else {},
            }

        result = request_task({"url": url, "timeout": timeout, "headers": headers or {}, "json_body": json_body})
        if result is None:
            raise RuntimeError("request retornou sem resposta")
        return HttpResponse(
            status_code=result.get("status_code"),
            url=result.get("url") or url,
            headers=result.get("headers") or {},
            text=result.get("text") or "",
            cookies=result.get("cookies") or {},
        )
