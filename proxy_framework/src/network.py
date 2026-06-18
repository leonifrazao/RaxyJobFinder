from __future__ import annotations

import base64
import ipaddress
import json
import logging
import re
import socket
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:
    requests = None

from .interfaces import ProxyNetworkManager, ProxyProcessManager
from .models import Outbound
from .parser import decode_bytes

logger = logging.getLogger(__name__)


class NetworkManager(ProxyNetworkManager):
    def __init__(self, requests_session: Any = None, process_manager: Optional[ProxyProcessManager] = None) -> None:
        self.requests = requests_session or requests
        self.process = process_manager

    @staticmethod
    def is_github_api_url(url: str) -> bool:
        return bool(re.match(r"^https://api\.github\.com/repos/.+/contents/.+", url, re.I))

    @staticmethod
    def is_github_raw_url(url: str) -> bool:
        return bool(re.match(r"^https://raw\.githubusercontent\.com/.+", url, re.I))

    @staticmethod
    def convert_raw_to_api_url(raw_url: str) -> str:
        match = re.match(r"^https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$", raw_url, re.I)
        if not match:
            logger.warning("URL raw do GitHub nao reconhecida: %s", raw_url)
            return raw_url
        owner, repo, ref, path = match.groups()
        return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"

    @staticmethod
    def decode_github_api_content(api_response: Dict[str, Any]) -> str:
        if not isinstance(api_response, dict):
            raise ValueError("Resposta da API deve ser um dicionario")
        content_b64 = api_response.get("content")
        if not content_b64:
            raise ValueError("Campo 'content' nao encontrado na resposta da API")
        try:
            cleaned_content = content_b64.replace("\n", "").replace("\r", "").strip()
            decoded_bytes = base64.b64decode(cleaned_content)
            return decoded_bytes.decode("utf-8")
        except base64.binascii.Error as exc:
            raise ValueError(f"Conteudo base64 invalido: {exc}") from exc
        except UnicodeDecodeError as exc:
            try:
                return decoded_bytes.decode("latin-1")
            except Exception:
                raise exc

    @staticmethod
    def validate_proxies(proxy_text: str) -> Tuple[bool, int, str]:
        if not proxy_text or not proxy_text.strip():
            return False, 0, "Nenhum conteudo de proxy encontrado"
        valid_schemes = ("ss://", "vmess://", "vless://", "trojan://")
        valid_count = 0
        for line in proxy_text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if any(line.lower().startswith(scheme) for scheme in valid_schemes):
                valid_count += 1
        if valid_count == 0:
            return False, 0, "Nenhuma proxy valida encontrada"
        return True, valid_count, f"{valid_count} proxy(s) valida(s) encontrada(s)"

    def fetch_github_api_content(self, api_url: str) -> str:
        if self.requests is None:
            raise RuntimeError("Instale requests para baixar URLs de proxy.")
        try:
            resp = self.requests.get(
                api_url,
                timeout=30,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "Proxy-Framework/0.1"},
            )
            if resp.status_code == 403:
                raise RuntimeError("Rate limit da API do GitHub excedido")
            if resp.status_code == 404:
                raise RuntimeError(f"Recurso nao encontrado na API do GitHub: {api_url}")
            resp.raise_for_status()
            try:
                api_response = resp.json()
            except json.JSONDecodeError as exc:
                raise ValueError(f"Resposta da API do GitHub invalida: {exc}") from exc
            decoded_content = self.decode_github_api_content(api_response)
            self.validate_proxies(decoded_content)
            return decoded_content
        except self.requests.exceptions.Timeout as exc:
            raise RuntimeError("Timeout ao acessar API do GitHub") from exc
        except self.requests.exceptions.ConnectionError as exc:
            raise RuntimeError("Erro de conexao ao acessar API do GitHub") from exc
        except self.requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Erro ao acessar API do GitHub: {exc}") from exc

    def read_source_text(self, source: str) -> str:
        if not re.match(r"^https?://", source, re.I):
            return decode_bytes(Path(source).read_bytes())
        if self.requests is None:
            return self.fetch_url_text(source)

        is_raw = self.is_github_raw_url(source)
        is_api = self.is_github_api_url(source)
        if is_raw or is_api:
            api_url = self.convert_raw_to_api_url(source) if is_raw else source
            try:
                return self.fetch_github_api_content(api_url)
            except Exception:
                if not is_raw:
                    raise

        try:
            resp = self.requests.get(source, timeout=30)
            resp.raise_for_status()
            return decode_bytes(resp.content, encoding_hint=resp.encoding or None)
        except self.requests.exceptions.Timeout as exc:
            raise RuntimeError(f"Timeout ao acessar {source}") from exc
        except self.requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Erro de conexao ao acessar {source}") from exc

    @staticmethod
    def fetch_url_text(source: str) -> str:
        req = Request(source, headers={"User-Agent": "Proxy-Framework/0.1"})
        try:
            with urlopen(req, timeout=30) as resp:
                data = resp.read()
                content_type = resp.headers.get_content_charset()
                return decode_bytes(data, encoding_hint=content_type)
        except TimeoutError as exc:
            raise RuntimeError(f"Timeout ao acessar {source}") from exc
        except OSError as exc:
            raise RuntimeError(f"Erro ao acessar {source}: {exc}") from exc

    @staticmethod
    def is_public_ip(ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return not (addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast or addr.is_link_local)

    def lookup_country(self, ip: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
        if not ip or self.requests is None or not self.is_public_ip(ip):
            return None
        try:
            resp = self.requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            country_code = data.get("country_code")
            country_name = data.get("country_name")
            label = country_name or country_code
            if not (label or country_code or country_name):
                return None
            return {"name": country_name, "code": country_code, "label": label}
        except Exception:
            return None

    def outbound_host_port(self, outbound: Outbound) -> Tuple[str, int]:
        proto = outbound.config.get("protocol")
        settings = outbound.config.get("settings", {})
        host = None
        port = None
        if proto == "shadowsocks":
            server = settings.get("servers", [{}])[0]
            host = server.get("address")
            port = server.get("port")
        elif proto in ("vmess", "vless"):
            vnext = settings.get("vnext", [{}])[0]
            host = vnext.get("address")
            port = vnext.get("port")
        elif proto == "trojan":
            server = settings.get("servers", [{}])[0]
            host = server.get("address")
            port = server.get("port")
        else:
            raise ValueError(f"Protocolo nao suportado para teste: {proto}")

        if host is None or port is None:
            raise ValueError(f"Host/port ausentes no outbound {outbound.tag} ({proto}).")
        try:
            return host, int(str(port).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Porta invalida no outbound {outbound.tag}: {port!r}") from exc

    def test_outbound(
        self,
        raw_uri: str,
        outbound: Outbound,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip",
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {"tag": outbound.tag, "protocol": outbound.config.get("protocol"), "uri": raw_uri}
        try:
            host, port = self.outbound_host_port(outbound)
        except Exception as exc:
            result["error"] = f"host/port nao identificados: {exc}"
            return result

        result["host"] = host
        result["port"] = port
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except Exception:
            infos = []
        ip = None
        ipv6 = None
        for info in infos:
            family, *_rest, sockaddr = info
            address = sockaddr[0]
            if family == socket.AF_INET:
                ip = address
                break
            if ipv6 is None and family == socket.AF_INET6:
                ipv6 = address
        result["ip"] = ip or ipv6

        if result.get("ip"):
            country_info = self.lookup_country(result["ip"])
            if country_info:
                result["country"] = country_info.get("label")
                result["country_code"] = country_info.get("code")
                result["country_name"] = country_info.get("name")

        func_result = self.test_proxy_functionality(raw_uri, outbound, timeout=timeout, test_url=test_url)
        if func_result.get("functional"):
            result["ping_ms"] = func_result.get("response_time")
            result["functional"] = True
            result["external_ip"] = func_result.get("external_ip")
            if func_result.get("external_ip") and func_result["external_ip"] != result.get("ip"):
                result["proxy_ip"] = func_result["external_ip"]
                proxy_country = self.lookup_country(func_result["external_ip"])
                if proxy_country:
                    result["proxy_country"] = proxy_country.get("label")
                    result["proxy_country_code"] = proxy_country.get("code")
        else:
            result["error"] = func_result.get("error", "Proxy nao funcional")
            result["functional"] = False
        return result

    def test_proxy_functionality(
        self,
        raw_uri: str,
        outbound: Outbound,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip",
    ) -> Dict[str, Any]:
        result = {"functional": False, "response_time": None, "external_ip": None, "error": None}
        if self.requests is None:
            result["error"] = "requests nao disponivel para teste funcional"
            return result
        if self.process is None:
            result["error"] = "process_manager nao configurado"
            return result

        exceptions_mod = getattr(self.requests, "exceptions", None)
        response = None
        duration_ms: Optional[float] = None
        try:
            with self.process.temporary_bridge(outbound, tag_prefix="test") as (test_port, _):
                proxy_url = f"http://127.0.0.1:{test_port}"
                proxies = {"http": proxy_url, "https": proxy_url}
                started_at = time.perf_counter()
                response = self.requests.get(
                    test_url,
                    proxies=proxies,
                    timeout=timeout,
                    verify=False,
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                    },
                )
                response.raise_for_status()
                duration_ms = (time.perf_counter() - started_at) * 1000
        except RuntimeError as exc:
            result["error"] = str(exc)
            return result
        except Exception as exc:
            result["error"] = self.format_request_error(exc, timeout, exceptions_mod)
            return result

        result["functional"] = True
        result["response_time"] = duration_ms
        if response is not None:
            result["external_ip"] = self.extract_external_ip(response)
        return result

    @staticmethod
    def matches_exception(exc: Exception, candidate: Any) -> bool:
        if candidate is None:
            return False
        try:
            return isinstance(exc, candidate)
        except TypeError:
            return False

    def format_request_error(self, exc: Exception, timeout: float, exceptions_mod: Any) -> str:
        timeout_exc = getattr(exceptions_mod, "Timeout", None) if exceptions_mod else None
        proxy_exc = getattr(exceptions_mod, "ProxyError", None) if exceptions_mod else None
        conn_exc = getattr(exceptions_mod, "ConnectionError", None) if exceptions_mod else None
        http_exc = getattr(exceptions_mod, "HTTPError", None) if exceptions_mod else None

        if self.matches_exception(exc, timeout_exc):
            return f"Timeout apos {timeout:.1f}s"
        if self.matches_exception(exc, proxy_exc):
            return f"Erro de proxy: {str(exc)[:100]}"
        if self.matches_exception(exc, conn_exc):
            return f"Erro de conexao: {str(exc)[:100]}"
        if self.matches_exception(exc, http_exc):
            response = getattr(exc, "response", None)
            if response is not None:
                return f"Erro HTTP {response.status_code}: {response.reason}"
        return f"Erro na requisicao: {str(exc)[:100]}"

    @staticmethod
    def extract_external_ip(response: Any) -> Optional[str]:
        try:
            data = response.json()
        except Exception:
            return None
        origin = data.get("origin")
        if isinstance(origin, str) and origin.strip():
            return origin.split(",")[0].strip()
        return None
