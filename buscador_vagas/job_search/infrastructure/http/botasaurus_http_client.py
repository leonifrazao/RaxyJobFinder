from __future__ import annotations

import socket
from urllib.parse import urlparse
from typing import Any

from botasaurus.request import Request, request as botasaurus_request
from botasaurus_requests.exceptions import ClientException

from job_search.application.dto.output.http_response import HttpResponse
from job_search.infrastructure.config import load_settings


class BotasaurusHttpClient:
    def _to_cookies(self, jar: Any) -> dict[str, str]:
        return {c.name: c.value for c in jar} if jar else {}

    @staticmethod
    def _check_bridge_reachable(bridge_url: str) -> None:
        parsed = urlparse(bridge_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        try:
            with socket.create_connection((host, port), timeout=load_settings().proxy.detection_timeout):
                pass
        except OSError as exc:
            raise RuntimeError(
                f"Ponte proxy {bridge_url} inalcancavel: {exc}. "
                "O Xray pode nao estar rodando ou a porta esta bloqueada."
            ) from exc

    def get(self, bridge_url: str, url: str, timeout: float, *, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        self._check_bridge_reachable(bridge_url)
        cfg = load_settings().defaults
        @botasaurus_request(
            proxy=bridge_url,
            output=None,
            max_retry=max_retry,
            close_on_crash=cfg.close_on_crash,
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

        try:
            result = request_task({"url": url, "timeout": timeout, "headers": headers or {}})
        except ClientException as exc:
            if load_settings().defaults.suppress_client_errors:
                return HttpResponse(
                    status_code=None,
                    url=url,
                    headers={},
                    text="",
                    cookies={},
                )
            raise RuntimeError(
                f"Proxy {bridge_url} falhou no GET {url}: {exc}"
            ) from exc
        if result is None:
            if load_settings().defaults.suppress_client_errors:
                return HttpResponse(
                    status_code=None,
                    url=url,
                    headers={},
                    text="",
                    cookies={},
                )
            raise RuntimeError("request retornou sem resposta")
        return HttpResponse(
            status_code=result.get("status_code"),
            url=result.get("url") or url,
            headers=result.get("headers") or {},
            text=result.get("text") or "",
            cookies=result.get("cookies") or {},
        )

    def post(self, bridge_url: str, url: str, timeout: float, *, json_body: dict[str, Any] | None = None, headers: dict[str, Any] | None = None, max_retry: int = 1) -> HttpResponse:
        self._check_bridge_reachable(bridge_url)
        cfg = load_settings().defaults
        @botasaurus_request(
            proxy=bridge_url,
            output=None,
            max_retry=max_retry,
            close_on_crash=cfg.close_on_crash,
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

        try:
            result = request_task({"url": url, "timeout": timeout, "headers": headers or {}, "json_body": json_body})
        except ClientException as exc:
            if load_settings().defaults.suppress_client_errors:
                return HttpResponse(
                    status_code=None,
                    url=url,
                    headers={},
                    text="",
                    cookies={},
                )
            raise RuntimeError(
                f"Proxy {bridge_url} falhou no POST {url}: {exc}"
            ) from exc
        if result is None:
            if load_settings().defaults.suppress_client_errors:
                return HttpResponse(
                    status_code=None,
                    url=url,
                    headers={},
                    text="",
                    cookies={},
                )
            raise RuntimeError("request retornou sem resposta")
        return HttpResponse(
            status_code=result.get("status_code"),
            url=result.get("url") or url,
            headers=result.get("headers") or {},
            text=result.get("text") or "",
            cookies=result.get("cookies") or {},
        )
