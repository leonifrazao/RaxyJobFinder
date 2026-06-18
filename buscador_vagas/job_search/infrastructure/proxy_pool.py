from __future__ import annotations

import sys
from pathlib import Path

from job_search.domain.dtos import BridgeEndpoint

try:
    from proxy_framework import create_proxy
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "proxy_framework"))
    from proxy_framework import create_proxy


class ProxyFrameworkPool:
    def __init__(self, *, provider_name: str, use_console: bool = True) -> None:
        self.provider_name = provider_name
        self.use_console = use_console
        self._proxy = None

    def prepare(self, *, sources: list[str], max_count: int, valid_count: int, threads: int, timeout: float, test_url: str) -> list[BridgeEndpoint]:
        self._proxy = create_proxy(
            sources=sources,
            max_count=max_count,
            use_cache=False,
            use_console=self.use_console,
        )
        results = self._proxy.test(
            threads=threads,
            timeout=timeout,
            test_url=test_url,
            force=True,
            find_first=valid_count,
        )
        working = [entry for entry in results if entry.result.status == "OK"]
        if not working:
            raise RuntimeError("Nenhuma proxy funcional encontrada para o portal.")

        active = self._proxy.start(amounts=valid_count, auto_test=False)
        return [BridgeEndpoint(index=index, url=item.uri) for index, item in enumerate(active)]

    def stop(self) -> None:
        if self._proxy is not None:
            self._proxy.stop()
