from __future__ import annotations

from typing import Protocol

from job_search.domain.proxy import BridgeEndpoint


class ProxyPool(Protocol):
    def prepare(self, *, sources: list[str], max_count: int, valid_count: int, threads: int, timeout: float, test_url: str) -> list[BridgeEndpoint]:
        ...

    def stop(self) -> None:
        ...
