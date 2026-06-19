from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from job_search.domain.proxy import BridgeEndpoint


class ProxyPool(Protocol):
    def prepare(
        self,
        *,
        sources: list[str],
        max_count: int,
        valid_count: int,
        threads: int,
        timeout: float,
        test_url: str,
        progress_callback: Callable[[str, str, dict], None] | None = None,
    ) -> list[BridgeEndpoint]:
        ...

    def stop(self) -> None:
        ...
