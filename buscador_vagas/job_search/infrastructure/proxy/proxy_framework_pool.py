from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from job_search.domain.proxy import BridgeEndpoint

try:
    from src import create_proxy
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "proxy_framework"))
    from src import create_proxy


class ProxyFrameworkPool:
    def __init__(self, *, provider_name: str, use_console: bool = True) -> None:
        self.provider_name = provider_name
        self.use_console = use_console
        self._proxy = None

    def prepare(self, *, sources: list[str], max_count: int, valid_count: int, threads: int, timeout: float, test_url: str) -> list[BridgeEndpoint]:
        log = logger.bind(
            component="proxy_pool",
            provider=self.provider_name,
            sources_count=len(sources),
            max_count=max_count,
            valid_count=valid_count,
            threads=threads,
            timeout=timeout,
            test_url=test_url,
        )
        log.info("proxy_prepare_started")
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
            log.bind(total_results=len(results), working_count=0).error("proxy_prepare_no_working_proxy")
            raise RuntimeError("Nenhuma proxy funcional encontrada para o portal.")

        active = self._proxy.start(amounts=valid_count, auto_test=False)
        bridges = [BridgeEndpoint(index=index, url=item.uri) for index, item in enumerate(active)]
        log.bind(total_results=len(results), working_count=len(working), bridges_count=len(bridges)).info("proxy_prepare_finished")
        return bridges

    def stop(self) -> None:
        if self._proxy is not None:
            logger.bind(component="proxy_pool", provider=self.provider_name).info("proxy_pool_stopping")
            self._proxy.stop()
