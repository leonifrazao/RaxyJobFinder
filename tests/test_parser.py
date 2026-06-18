from __future__ import annotations

import pytest

from src.parser import (
    b64decode_padded,
    decode_bytes,
    parse_ss,
    parse_trojan,
    parse_uri_to_outbound,
    parse_vless,
    parse_vmess,
    safe_int,
    sanitize_tag,
    vmess_outbound_from_dict,
)


class TestB64DecodePadded:
    def test_pads_and_decodes(self):
        result = b64decode_padded("dGVzdA")
        assert result == b"test"

    def test_already_padded(self):
        result = b64decode_padded("dGVzdA==")
        assert result == b"test"


class TestDecodeBytes:
    def test_utf8(self):
        assert decode_bytes(b"hello") == "hello"

    def test_not_bytes(self):
        assert decode_bytes("not bytes") == "not bytes"

    def test_fallback_encoding(self):
        data = "café".encode("latin-1")
        assert decode_bytes(data) == "café"


class TestSanitizeTag:
    def test_none_uses_fallback(self):
        assert sanitize_tag(None, "fallback") == "fallback"

    def test_empty_uses_fallback(self):
        assert sanitize_tag("", "fallback") == "fallback"

    def test_replaces_special_chars(self):
        assert sanitize_tag("my tag!@#", "fb") == "my_tag_"

    def test_truncates_to_48_chars(self):
        long_tag = "a" * 100
        result = sanitize_tag(long_tag, "fb")
        assert len(result) == 48

    def test_all_special_chars_replaced_by_single_underscore(self):
        assert sanitize_tag("!@#$%", "fb") == "_"


class TestSafeInt:
    def test_valid_int(self):
        assert safe_int("42") == 42

    def test_none_returns_none(self):
        assert safe_int(None) is None

    def test_invalid_string_returns_none(self):
        assert safe_int("abc") is None


class TestParseUriToOutbound:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="vazia|comentario"):
            parse_uri_to_outbound("")

    def test_comment_raises(self):
        with pytest.raises(ValueError, match="vazia|comentario"):
            parse_uri_to_outbound("# comment")

    def test_unknown_scheme_raises(self):
        with pytest.raises(ValueError, match="suportado"):
            parse_uri_to_outbound("unknown://something")

    def test_http_scheme_raises(self):
        with pytest.raises(ValueError, match="suportado"):
            parse_uri_to_outbound("http://example.com")

    def test_dispatches_ss(self):
        uri = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ@example.com:8443"
        result = parse_uri_to_outbound(uri)
        assert result.tag == "ss"
        assert result.config["protocol"] == "shadowsocks"

    def test_dispatches_vmess(self):
        uri = "vmess://eyJhZGQiOiIxLjEuMS4xIiwicG9ydCI6ODQ0MywiaWQiOiJhYmMxMjMiLCJwcyI6InZtZXNzLXRlc3QifQ"
        result = parse_uri_to_outbound(uri)
        assert result.tag == "vmess-test"
        assert result.config["protocol"] == "vmess"

    def test_dispatches_vless(self):
        uri = "vless://abc123@example.com:443?security=tls"
        result = parse_uri_to_outbound(uri)
        assert result.config["protocol"] == "vless"

    def test_dispatches_trojan(self):
        uri = "trojan://password@example.com:443"
        result = parse_uri_to_outbound(uri)
        assert result.config["protocol"] == "trojan"

    def test_strips_uri(self):
        result = parse_uri_to_outbound("  ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ@a.com:80  ")
        assert result.config["protocol"] == "shadowsocks"


class TestParseSS:
    def test_standard_format(self):
        import base64
        userinfo = base64.urlsafe_b64encode(b"aes-256-gcm:password").decode().rstrip("=")
        uri = f"ss://{userinfo}@example.com:8443#my-tag"
        result = parse_ss(uri)
        assert result.tag == "my-tag"
        assert result.config["settings"]["servers"][0]["address"] == "example.com"
        assert result.config["settings"]["servers"][0]["port"] == 8443
        assert result.config["settings"]["servers"][0]["method"] == "aes-256-gcm"
        assert result.config["settings"]["servers"][0]["password"] == "password"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="invalido"):
            parse_ss("ss://invalid")

    def test_invalid_port_raises(self):
        import base64
        userinfo = base64.urlsafe_b64encode(b"method:pass").decode().rstrip("=")
        uri = f"ss://{userinfo}@host:notaport"
        with pytest.raises(ValueError, match="Porta ss invalida"):
            parse_ss(uri)


class TestParseVmess:
    def test_json_format(self):
        import json, base64
        data = {"add": "1.2.3.4", "port": 443, "id": "uuid-123", "ps": "my-vmess", "net": "tcp"}
        encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        uri = f"vmess://{encoded}"
        result = parse_vmess(uri)
        assert result.tag == "my-vmess"
        assert result.config["protocol"] == "vmess"
        assert result.config["settings"]["vnext"][0]["address"] == "1.2.3.4"
        assert result.config["settings"]["vnext"][0]["port"] == 443

    def test_invalid_base64_raises(self):
        with pytest.raises(ValueError, match="decodificar"):
            parse_vmess("vmess://invalid!!!base64")

    def test_minimal_vmess(self):
        import json, base64
        data = {"add": "5.6.7.8", "port": 8080, "id": "abc-def"}
        encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        result = parse_vmess(f"vmess://{encoded}")
        assert result.config["settings"]["vnext"][0]["address"] == "5.6.7.8"

    def test_ws_transport(self):
        import json, base64
        data = {"add": "1.1.1.1", "port": 443, "id": "u1", "net": "ws", "path": "/ws", "host": "example.com"}
        encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        result = parse_vmess(f"vmess://{encoded}")
        assert result.config["streamSettings"]["network"] == "ws"
        assert result.config["streamSettings"]["wsSettings"]["path"] == "/ws"
        assert result.config["streamSettings"]["wsSettings"]["headers"]["Host"] == "example.com"

    def test_grpc_transport(self):
        import json, base64
        data = {"add": "1.1.1.1", "port": 443, "id": "u1", "net": "grpc", "serviceName": "svc"}
        encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
        result = parse_vmess(f"vmess://{encoded}")
        assert result.config["streamSettings"]["network"] == "grpc"
        assert result.config["streamSettings"]["grpcSettings"]["serviceName"] == "svc"


class TestVmessOutboundFromDict:
    def test_minimal(self):
        result = vmess_outbound_from_dict({"add": "1.2.3.4", "port": 443, "id": "uuid"})
        assert result.config["settings"]["vnext"][0]["address"] == "1.2.3.4"

    def test_missing_host_raises(self):
        with pytest.raises(ValueError, match="incompleto"):
            vmess_outbound_from_dict({"port": 443, "id": "uuid"})

    def test_missing_id_raises(self):
        with pytest.raises(ValueError, match="incompleto"):
            vmess_outbound_from_dict({"add": "1.2.3.4", "port": 443})

    def test_tls_settings(self):
        result = vmess_outbound_from_dict({"add": "1.1.1.1", "port": 443, "id": "u", "tls": "tls", "sni": "example.com"})
        assert result.config["streamSettings"]["security"] == "tls"
        assert result.config["streamSettings"]["tlsSettings"]["serverName"] == "example.com"


class TestParseVless:
    def test_minimal(self):
        result = parse_vless("vless://uuid@host.com:443")
        assert result.config["protocol"] == "vless"
        assert result.config["settings"]["vnext"][0]["address"] == "host.com"
        assert result.config["settings"]["vnext"][0]["port"] == 443

    def test_incomplete_raises(self):
        with pytest.raises(ValueError, match="incompleto"):
            parse_vless("vless://host.com:443")

    def test_with_flow(self):
        result = parse_vless("vless://uuid@host.com:443?flow=xtls-rprx-vision")
        assert result.config["settings"]["vnext"][0]["users"][0]["flow"] == "xtls-rprx-vision"

    def test_ws_transport(self):
        result = parse_vless("vless://uuid@host.com:443?type=ws&path=/ws&host=x.com&security=tls")
        assert result.config["streamSettings"]["network"] == "ws"
        assert result.config["streamSettings"]["security"] == "tls"
        assert result.config["streamSettings"]["wsSettings"]["path"] == "/ws"

    def test_reality(self):
        result = parse_vless("vless://uuid@host.com:443?security=reality&sni=example.com&fp=chrome")
        assert result.config["streamSettings"]["security"] == "reality"
        assert "realitySettings" in result.config["streamSettings"]

    def test_grpc_transport(self):
        result = parse_vless("vless://uuid@host.com:443?type=grpc&serviceName=svc")
        assert result.config["streamSettings"]["network"] == "grpc"
        assert result.config["streamSettings"]["grpcSettings"]["serviceName"] == "svc"


class TestParseTrojan:
    def test_minimal(self):
        result = parse_trojan("trojan://password@host.com:443")
        assert result.config["protocol"] == "trojan"
        assert result.config["settings"]["servers"][0]["address"] == "host.com"
        assert result.config["settings"]["servers"][0]["port"] == 443
        assert result.config["settings"]["servers"][0]["password"] == "password"

    def test_incomplete_raises(self):
        with pytest.raises(ValueError, match="incompleto"):
            parse_trojan("trojan://host.com:443")

    def test_with_sni_and_alpn(self):
        result = parse_trojan("trojan://pass@host.com:443?sni=x.com&alpn=h2&alpn=http/1.1")
        assert result.config["streamSettings"]["security"] == "tls"
        assert result.config["streamSettings"]["tlsSettings"]["serverName"] == "x.com"
        assert "alpn" in result.config["streamSettings"]["tlsSettings"]

    def test_ws_transport(self):
        result = parse_trojan("trojan://pass@host.com:443?type=ws&path=/ws&host=x.com")
        assert result.config["streamSettings"]["network"] == "ws"
        assert result.config["streamSettings"]["wsSettings"]["path"] == "/ws"

    def test_grpc_transport(self):
        result = parse_trojan("trojan://pass@host.com:443?type=grpc&serviceName=svc")
        assert result.config["streamSettings"]["network"] == "grpc"
        assert result.config["streamSettings"]["grpcSettings"]["serviceName"] == "svc"
