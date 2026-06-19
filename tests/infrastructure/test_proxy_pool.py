from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from job_search.domain.proxy import BridgeEndpoint
from job_search.infrastructure.proxy_pool import ProxyFrameworkPool


@pytest.fixture
def mock_proxy() -> MagicMock:
    proxy = MagicMock()
    proxy.test.return_value = []
    proxy.start.return_value = []
    proxy.stop.return_value = None
    return proxy


@pytest.fixture
def pool() -> ProxyFrameworkPool:
    return ProxyFrameworkPool(provider_name="test", use_console=False)


class TestPrepare:
    def test_returns_bridge_endpoints(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        mock_item_0 = MagicMock()
        mock_item_0.uri = "socks5://127.0.0.1:1080"
        mock_item_1 = MagicMock()
        mock_item_1.uri = "socks5://127.0.0.1:1081"

        mock_entry = MagicMock()
        mock_entry.result.status = "OK"

        mock_proxy.test.return_value = [mock_entry, mock_entry]
        mock_proxy.start.return_value = [mock_item_0, mock_item_1]

        with patch("job_search.infrastructure.proxy_pool.create_proxy", return_value=mock_proxy):
            result = pool.prepare(
                sources=["https://example.com/proxies"],
                max_count=100,
                valid_count=2,
                threads=4,
                timeout=10.0,
                test_url="http://httpbin.org/ip",
            )

        assert len(result) == 2
        assert isinstance(result[0], BridgeEndpoint)
        assert result[0].index == 0
        assert result[0].url == "socks5://127.0.0.1:1080"
        assert result[1].index == 1
        assert result[1].url == "socks5://127.0.0.1:1081"

    def test_passes_correct_args_to_create_proxy(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        captured: dict = {}

        mock_entry = MagicMock()
        mock_entry.result.status = "OK"

        mock_proxy.test.return_value = [mock_entry]
        mock_proxy.start.return_value = [MagicMock(uri="socks5://127.0.0.1:1080")]

        def fake_create_proxy(*, sources, max_count, use_cache, use_console):
            captured["sources"] = sources
            captured["max_count"] = max_count
            captured["use_cache"] = use_cache
            captured["use_console"] = use_console
            return mock_proxy

        with patch("job_search.infrastructure.proxy_pool.create_proxy", side_effect=fake_create_proxy):
            pool.prepare(
                sources=["src1", "src2"],
                max_count=50,
                valid_count=1,
                threads=2,
                timeout=5.0,
                test_url="http://check.torproject.org",
            )

        assert captured["sources"] == ["src1", "src2"]
        assert captured["max_count"] == 50
        assert captured["use_cache"] is False
        assert captured["use_console"] is False

    def test_passes_correct_args_to_proxy_test(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        captured: dict = {}

        mock_entry = MagicMock()
        mock_entry.result.status = "OK"

        mock_proxy.test.return_value = [mock_entry]
        mock_proxy.start.return_value = [MagicMock(uri="socks5://127.0.0.1:1080")]

        def fake_proxy_test(*, threads, timeout, test_url, force, find_first):
            captured["threads"] = threads
            captured["timeout"] = timeout
            captured["test_url"] = test_url
            captured["force"] = force
            captured["find_first"] = find_first
            return [mock_entry]

        mock_proxy.test.side_effect = fake_proxy_test

        with patch("job_search.infrastructure.proxy_pool.create_proxy", return_value=mock_proxy):
            pool.prepare(
                sources=["src"],
                max_count=100,
                valid_count=3,
                threads=8,
                timeout=15.0,
                test_url="http://httpbin.org/ip",
            )

        assert captured["threads"] == 8
        assert captured["timeout"] == 15.0
        assert captured["test_url"] == "http://httpbin.org/ip"
        assert captured["force"] is True
        assert captured["find_first"] == 3

    def test_passes_valid_count_to_start(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        mock_entry = MagicMock()
        mock_entry.result.status = "OK"

        mock_proxy.test.return_value = [mock_entry, mock_entry, mock_entry]
        mock_proxy.start.return_value = [
            MagicMock(uri="socks5://127.0.0.1:1080"),
            MagicMock(uri="socks5://127.0.0.1:1081"),
            MagicMock(uri="socks5://127.0.0.1:1082"),
        ]

        with patch("job_search.infrastructure.proxy_pool.create_proxy", return_value=mock_proxy):
            pool.prepare(
                sources=["src"],
                max_count=100,
                valid_count=3,
                threads=4,
                timeout=10.0,
                test_url="http://httpbin.org/ip",
            )

        mock_proxy.start.assert_called_once_with(amounts=3, auto_test=False)

    def test_no_working_proxies_raises(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        mock_failed = MagicMock()
        mock_failed.result.status = "FAIL"

        mock_proxy.test.return_value = [mock_failed]

        with patch("job_search.infrastructure.proxy_pool.create_proxy", return_value=mock_proxy):
            with pytest.raises(RuntimeError, match="Nenhuma proxy funcional"):
                pool.prepare(
                    sources=["src"],
                    max_count=10,
                    valid_count=1,
                    threads=1,
                    timeout=5.0,
                    test_url="http://httpbin.org/ip",
                )

    def test_empty_test_results_raises(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        mock_proxy.test.return_value = []

        with patch("job_search.infrastructure.proxy_pool.create_proxy", return_value=mock_proxy):
            with pytest.raises(RuntimeError, match="Nenhuma proxy funcional"):
                pool.prepare(
                    sources=["src"],
                    max_count=10,
                    valid_count=1,
                    threads=1,
                    timeout=5.0,
                    test_url="http://httpbin.org/ip",
                )


class TestStop:
    def test_stops_proxy(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        mock_entry = MagicMock()
        mock_entry.result.status = "OK"

        mock_proxy.test.return_value = [mock_entry]
        mock_proxy.start.return_value = [MagicMock(uri="socks5://127.0.0.1:1080")]

        with patch("job_search.infrastructure.proxy_pool.create_proxy", return_value=mock_proxy):
            pool.prepare(
                sources=["src"],
                max_count=10,
                valid_count=1,
                threads=1,
                timeout=5.0,
                test_url="http://httpbin.org/ip",
            )

        pool.stop()
        mock_proxy.stop.assert_called_once()

    def test_stop_without_prepare_does_not_raise(self, pool: ProxyFrameworkPool):
        pool.stop()

    def test_stop_called_twice(self, pool: ProxyFrameworkPool, mock_proxy: MagicMock):
        mock_entry = MagicMock()
        mock_entry.result.status = "OK"

        mock_proxy.test.return_value = [mock_entry]
        mock_proxy.start.return_value = [MagicMock(uri="socks5://127.0.0.1:1080")]

        with patch("job_search.infrastructure.proxy_pool.create_proxy", return_value=mock_proxy):
            pool.prepare(
                sources=["src"],
                max_count=10,
                valid_count=1,
                threads=1,
                timeout=5.0,
                test_url="http://httpbin.org/ip",
            )

        pool.stop()
        pool.stop()
        assert mock_proxy.stop.call_count == 2
