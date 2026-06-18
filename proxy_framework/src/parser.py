from __future__ import annotations

import base64
import html
import json
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse, urlsplit

from .models import Outbound


def b64decode_padded(value: str) -> bytes:
    value = value.strip()
    missing = (-len(value)) % 4
    if missing:
        value += "=" * missing
    return base64.urlsafe_b64decode(value)


def decode_bytes(data: bytes, *, encoding_hint: Optional[str] = None) -> str:
    if not isinstance(data, (bytes, bytearray)):
        return str(data)
    encodings = []
    if encoding_hint:
        encodings.append(encoding_hint)
    encodings.extend(["utf-8", "utf-8-sig", "latin-1"])
    tried = set()
    for enc in encodings:
        if not enc or enc in tried:
            continue
        tried.add(enc)
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def sanitize_tag(tag: Optional[str], fallback: str) -> str:
    if not tag:
        return fallback
    tag = re.sub(r"[^\w\-\.]+", "_", tag)
    return tag[:48] or fallback


def safe_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_uri_to_outbound(uri: str) -> Outbound:
    uri = uri.strip()
    if not uri or uri.startswith("#") or uri.startswith("//"):
        raise ValueError("Linha vazia ou comentario.")
    match = re.match(r"^([a-z0-9]+)://", uri, re.I)
    if not match:
        raise ValueError(f"Esquema desconhecido na linha: {uri[:80]}")
    scheme = match.group(1).lower()
    parser = {
        "ss": parse_ss,
        "vmess": parse_vmess,
        "vless": parse_vless,
        "trojan": parse_trojan,
    }.get(scheme)
    if parser is None:
        raise ValueError(f"Esquema nao suportado: {scheme}")
    return parser(uri)


def parse_ss(uri: str) -> Outbound:
    frag = urlsplit(uri).fragment
    tag = sanitize_tag(unquote(frag) if frag else None, "ss")
    payload = uri.strip()[5:]
    stripped_payload = payload.split("#")[0]

    try:
        decoded_preview = decode_bytes(b64decode_padded(stripped_payload))
    except Exception:
        decoded_preview = None

    if decoded_preview:
        text_preview = decoded_preview.strip()
        if text_preview.startswith("{") and text_preview.endswith("}"):
            try:
                data_json = json.loads(text_preview)
            except json.JSONDecodeError:
                pass
            else:
                known_keys = {"server", "method"}.issubset(data_json.keys()) or {"address", "method"}.issubset(data_json.keys()) or {"server", "password"}.issubset(data_json.keys())
                if known_keys:
                    ss_host = data_json.get("server") or data_json.get("address")
                    ss_port_raw = data_json.get("server_port") or data_json.get("port")
                    ss_method = data_json.get("method") or data_json.get("cipher")
                    ss_password = data_json.get("password") or data_json.get("passwd") or ""
                    if not ss_host or not ss_port_raw or not ss_method:
                        raise ValueError("Link ss:// incompleto.")
                    try:
                        ss_port = int(str(ss_port_raw).strip())
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"Porta ss invalida: {ss_port_raw!r}") from exc
                    return Outbound(tag, {
                        "tag": tag,
                        "protocol": "shadowsocks",
                        "settings": {"servers": [{
                            "address": ss_host,
                            "port": ss_port,
                            "method": ss_method,
                            "password": ss_password,
                        }]},
                    })

    at_split = stripped_payload.rsplit("@", 1)
    if len(at_split) != 2:
        raise ValueError("Formato ss:// invalido.")
    userinfo_b64, hostport = at_split
    try:
        userinfo = decode_bytes(b64decode_padded(userinfo_b64))
    except Exception as exc:
        raise ValueError(f"Falha no base64 do ss://: {exc}") from exc
    if ":" not in userinfo:
        raise ValueError("Formato userinfo ss:// invalido.")
    method, password = userinfo.split(":", 1)
    if ":" not in hostport:
        raise ValueError("Host ou porta ausentes no link ss://.")
    host, port_raw = hostport.split(":", 1)
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError(f"Porta ss invalida: {port_raw!r}") from exc

    return Outbound(tag, {
        "tag": tag,
        "protocol": "shadowsocks",
        "settings": {"servers": [{
            "address": host,
            "port": port,
            "method": method,
            "password": password,
        }]},
    })


def parse_vmess(uri: str) -> Outbound:
    payload = uri.strip()[8:]
    try:
        decoded = decode_bytes(b64decode_padded(payload))
    except Exception as exc:
        raise ValueError(f"Erro ao decodificar vmess://: {exc}") from exc
    try:
        data = json.loads(decoded)
    except json.JSONDecodeError:
        return vmess_outbound_from_uri(decoded)
    return vmess_outbound_from_dict(data)


def vmess_outbound_from_uri(decoded: str) -> Outbound:
    text = html.unescape(decoded).strip()
    text = re.sub(r"<br\s*/?>.*$", "", text, flags=re.I | re.S).strip()
    if text.startswith("vmess://"):
        return parse_vmess(text)
    if "://" not in text:
        text = f"vmess://{text}"

    parsed = urlparse(text)
    uuid = parsed.username
    host = parsed.hostname
    port = parsed.port
    q = parse_qs(parsed.query or "")

    if not uuid or not host or not port:
        raise ValueError("vmess:// nao-JSON incompleto.")

    tag = sanitize_tag(unquote(parsed.fragment) if parsed.fragment else q.get("remarks", [None])[0], "vmess")
    net = (q.get("type") or q.get("net") or ["tcp"])[0].lower()
    security = (q.get("security") or q.get("tls") or ["none"])[0].lower()
    tls = security in ("tls", "1", "true")
    sni = (q.get("sni") or q.get("serverName") or q.get("host") or [None])[0]
    host_header = (q.get("host") or [None])[0]
    path = (q.get("path") or ["/"])[0]
    service_name = (q.get("serviceName") or [""])[0]

    data = {
        "ps": tag,
        "add": host,
        "port": port,
        "id": uuid,
        "aid": q.get("alterId", q.get("aid", [0]))[0],
        "scy": (q.get("encryption") or q.get("scy") or ["auto"])[0],
        "net": net,
        "tls": "tls" if tls else "none",
        "sni": sni,
        "host": host_header,
        "path": path,
        "serviceName": service_name,
    }
    return vmess_outbound_from_dict(data)


def vmess_outbound_from_dict(data: Dict[str, Any], *, tag_fallback: str = "vmess") -> Outbound:
    tag = sanitize_tag(data.get("ps"), tag_fallback)
    host = data.get("add") or data.get("address")
    port_raw = data.get("port", 0)
    try:
        port = int(str(port_raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Porta vmess invalida: {port_raw!r}") from exc

    uuid = data.get("id")
    if not host or not port or not uuid:
        raise ValueError("vmess:// incompleto.")

    try:
        alter_id = int(str(data.get("aid", 0)).strip() or "0")
    except (TypeError, ValueError):
        alter_id = 0

    net = str(data.get("net") or data.get("network") or "tcp").lower()
    tls_flag = str(data.get("tls") or data.get("security") or "").lower()
    tls = tls_flag == "tls"
    security = "tls" if tls else "none"
    sni = data.get("sni") or data.get("host")
    path = data.get("path") or "/"
    host_header = data.get("host")

    if net == "ws":
        transport = {"network": "ws", "wsSettings": {"path": path or "/", "headers": {"Host": host_header} if host_header else {}}}
    elif net == "grpc":
        service_name = data.get("serviceName") or (path or "/").lstrip("/")
        transport = {"network": "grpc", "grpcSettings": {"serviceName": service_name}}
    else:
        transport = {"network": "tcp"}

    outbound_config = {
        "tag": tag,
        "protocol": "vmess",
        "settings": {"vnext": [{
            "address": host,
            "port": port,
            "users": [{"id": uuid, "alterId": alter_id, "security": data.get("scy") or "auto"}],
        }]},
        "streamSettings": {"security": security, **transport},
    }

    if tls and sni:
        outbound_config["streamSettings"]["tlsSettings"] = {"serverName": sni}
    return Outbound(tag, outbound_config)


def parse_vless(uri: str) -> Outbound:
    p = urlparse(uri)
    tag = sanitize_tag(unquote(p.fragment) if p.fragment else None, "vless")
    uuid = p.username
    host = p.hostname
    port = p.port
    q = parse_qs(p.query or "")
    flow = q.get("flow", [""])[0]
    security = q.get("security", ["none"])[0]
    sni = q.get("sni", [None])[0]
    alpn = q.get("alpn", [])
    net = q.get("type", ["tcp"])[0]
    path = q.get("path", ["/"])[0]
    host_header = q.get("host", [None])[0]
    service_name = q.get("serviceName", [""])[0]

    if not uuid or not host or not port:
        raise ValueError("vless:// incompleto.")

    if net == "ws":
        transport: Dict[str, Any] = {"network": "ws", "wsSettings": {"path": path, "headers": {"Host": host_header} if host_header else {}}}
    elif net == "grpc":
        transport = {"network": "grpc", "grpcSettings": {"serviceName": service_name}}
    else:
        transport = {"network": "tcp"}

    stream: Dict[str, Any] = {"security": "none", **transport}
    if security in ("tls", "reality"):
        stream["security"] = security
        tls_key = "tlsSettings" if security == "tls" else "realitySettings"
        tls_settings: Dict[str, Any] = {}
        if sni:
            tls_settings["serverName"] = sni
        if alpn:
            tls_settings["alpn"] = alpn
        stream[tls_key] = tls_settings

    return Outbound(tag, {
        "tag": tag,
        "protocol": "vless",
        "settings": {"vnext": [{
            "address": host,
            "port": port,
            "users": [{"id": uuid, "encryption": q.get("encryption", ["none"])[0], "flow": flow}],
        }]},
        "streamSettings": stream,
    })


def parse_trojan(uri: str) -> Outbound:
    p = urlparse(uri)
    tag = sanitize_tag(unquote(p.fragment) if p.fragment else None, "trojan")
    password = unquote(p.username or "")
    host = p.hostname
    port = p.port
    q = parse_qs(p.query or "")
    security = (q.get("security", ["tls"])[0]).lower()
    sni = q.get("sni", [None])[0]
    alpn = q.get("alpn", [])
    net = (q.get("type", ["tcp"])[0]).lower()
    path = q.get("path", ["/"])[0]
    host_header = q.get("host", [None])[0]
    service_name = q.get("serviceName", [""])[0]

    if not password or not host or not port:
        raise ValueError("trojan:// incompleto.")

    if net == "ws":
        transport: Dict[str, Any] = {"network": "ws", "wsSettings": {"path": path, "headers": {"Host": host_header} if host_header else {}}}
    elif net == "grpc":
        transport = {"network": "grpc", "grpcSettings": {"serviceName": service_name}}
    else:
        transport = {"network": "tcp"}

    stream: Dict[str, Any] = {"security": "none", **transport}
    if security in ("tls", "reality"):
        stream["security"] = security
        tls_key = "tlsSettings" if security == "tls" else "realitySettings"
        tls_settings: Dict[str, Any] = {}
        if sni:
            tls_settings["serverName"] = sni
        if alpn:
            tls_settings["alpn"] = alpn
        stream[tls_key] = tls_settings

    return Outbound(tag, {
        "tag": tag,
        "protocol": "trojan",
        "settings": {"servers": [{"address": host, "port": port, "password": password, "flow": ""}]},
        "streamSettings": stream,
    })
