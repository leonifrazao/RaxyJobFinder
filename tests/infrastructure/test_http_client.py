from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from job_search.infrastructure.http_client import BotasaurusHttpClient

PATCH_TARGET = "job_search.infrastructure.http_client.botasaurus_request"


@pytest.fixture
def client() -> BotasaurusHttpClient:
    return BotasaurusHttpClient()


class TestGet:
    def test_returns_http_response(self, client: BotasaurusHttpClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/result"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = "<html>ok</html>"
        mock_response.cookies = {"session": "abc"}

        def make_decorator(**kwargs):
            def deco(func):
                def wrapper(*args, **kwargs2):
                    mock_req = MagicMock()
                    mock_req.get.return_value = mock_response
                    return func(mock_req, {"url": "https://example.com", "timeout": 10.0, "headers": {}})
                return wrapper
            return deco

        with patch(PATCH_TARGET, side_effect=make_decorator):
            with patch.object(client, "_to_cookies", return_value={"session": "abc"}):
                result = client.get("http://bridge:8080", "https://example.com", 10.0)

        assert result.status_code == 200
        assert result.url == "https://example.com/result"
        assert result.headers == {"Content-Type": "text/html"}
        assert result.text == "<html>ok</html>"
        assert result.cookies == {"session": "abc"}

    def test_none_result_raises(self, client: BotasaurusHttpClient):
        def make_decorator(**kwargs):
            def deco(func):
                def wrapper(*args, **kwargs2):
                    mock_req = MagicMock()
                    mock_req.get.return_value.status_code = 200
                    mock_req.get.return_value.url = ""
                    mock_req.get.return_value.headers = {}
                    mock_req.get.return_value.text = ""
                    mock_req.get.return_value.cookies = {}
                    return None
                return wrapper
            return deco

        with patch(PATCH_TARGET, side_effect=make_decorator):
            with pytest.raises(RuntimeError, match="request retornou sem resposta"):
                client.get("http://bridge:8080", "https://example.com", 10.0)

    def test_passes_headers(self, client: BotasaurusHttpClient):
        captured: dict = {}

        def make_decorator(**kwargs):
            def deco(func):
                def wrapper(*args, **kwargs2):
                    mock_req = MagicMock()
                    mock_req.get.return_value.status_code = 200
                    mock_req.get.return_value.url = ""
                    mock_req.get.return_value.headers = {}
                    mock_req.get.return_value.text = ""
                    mock_req.get.return_value.cookies = {}
                    data = {"url": "https://example.com", "timeout": 5.0, "headers": {"Authorization": "Bearer x"}}
                    captured["data"] = data
                    return func(mock_req, data)
                return wrapper
            return deco

        with patch(PATCH_TARGET, side_effect=make_decorator):
            client.get("http://bridge:8080", "https://example.com", 5.0, headers={"Authorization": "Bearer x"})

        assert captured["data"]["headers"] == {"Authorization": "Bearer x"}

    def test_default_max_retry(self, client: BotasaurusHttpClient):
        kwargs_captured: dict = {}

        def make_decorator(**kwargs):
            kwargs_captured.update(kwargs)
            def deco(func):
                def wrapper(*args, **kwargs2):
                    mock_req = MagicMock()
                    mock_req.get.return_value.status_code = 200
                    mock_req.get.return_value.url = ""
                    mock_req.get.return_value.headers = {}
                    mock_req.get.return_value.text = ""
                    mock_req.get.return_value.cookies = {}
                    return func(mock_req, {"url": "", "timeout": 10.0, "headers": {}})
                return wrapper
            return deco

        with patch(PATCH_TARGET, side_effect=make_decorator):
            client.get("http://bridge:8080", "https://example.com", 10.0)

        assert kwargs_captured.get("max_retry") == 1


class TestPost:
    def test_returns_http_response(self, client: BotasaurusHttpClient):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.url = "https://example.com/created"
        mock_response.headers = {"Location": "/resource/1"}
        mock_response.text = '{"id": 1}'
        mock_response.cookies = {}

        def make_decorator(**kwargs):
            def deco(func):
                def wrapper(*args, **kwargs2):
                    mock_req = MagicMock()
                    mock_req.post.return_value = mock_response
                    return func(mock_req, {"url": "https://example.com", "timeout": 10.0, "headers": {}, "json_body": {"name": "test"}})
                return wrapper
            return deco

        with patch(PATCH_TARGET, side_effect=make_decorator):
            result = client.post("http://bridge:8080", "https://example.com", 10.0, json_body={"name": "test"})

        assert result.status_code == 201
        assert result.text == '{"id": 1}'

    def test_sets_content_type_header(self, client: BotasaurusHttpClient):
        captured: dict = {}

        def make_decorator(**kwargs):
            def deco(func):
                def wrapper(*args, **kwargs2):
                    mock_req = MagicMock()
                    mock_req.post.return_value.status_code = 200
                    mock_req.post.return_value.url = ""
                    mock_req.post.return_value.headers = {}
                    mock_req.post.return_value.text = ""
                    mock_req.post.return_value.cookies = {}
                    func(mock_req, {"url": "", "timeout": 10.0, "headers": {}, "json_body": {"k": "v"}})
                    captured["headers"] = mock_req.post.call_args[1].get("headers", {})
                    return {"status_code": 200, "url": "", "headers": {}, "text": "", "cookies": {}}
                return wrapper
            return deco

        with patch(PATCH_TARGET, side_effect=make_decorator):
            client.post("http://bridge:8080", "https://example.com", 10.0, json_body={"k": "v"})

        assert captured["headers"].get("Content-Type") == "application/json"

    def test_none_result_raises(self, client: BotasaurusHttpClient):
        def make_decorator(**kwargs):
            def deco(func):
                def wrapper(*args, **kwargs2):
                    mock_req = MagicMock()
                    mock_req.post.return_value.status_code = 200
                    mock_req.post.return_value.url = ""
                    mock_req.post.return_value.headers = {}
                    mock_req.post.return_value.text = ""
                    mock_req.post.return_value.cookies = {}
                    return None
                return wrapper
            return deco

        with patch(PATCH_TARGET, side_effect=make_decorator):
            with pytest.raises(RuntimeError, match="request retornou sem resposta"):
                client.post("http://bridge:8080", "https://example.com", 10.0)


class TestToCookies:
    def test_empty_jar_returns_empty(self):
        client = BotasaurusHttpClient()
        assert client._to_cookies(None) == {}

    def test_with_cookies(self):
        client = BotasaurusHttpClient()
        mock_jar = [MagicMock(name="session"), MagicMock(name="token")]
        mock_jar[0].name = "session"
        mock_jar[0].value = "abc123"
        mock_jar[1].name = "token"
        mock_jar[1].value = "xyz"
        result = client._to_cookies(mock_jar)
        assert result == {"session": "abc123", "token": "xyz"}

    def test_empty_list_returns_empty(self):
        client = BotasaurusHttpClient()
        assert client._to_cookies([]) == {}
