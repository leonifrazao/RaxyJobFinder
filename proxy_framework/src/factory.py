from __future__ import annotations

from typing import Any, Iterable, Optional

from .interfaces import ProxyNetworkManager, ProxyProcessManager
from .manager import Proxy


def create_proxy(
    proxies: Optional[Iterable[str]] = None,
    sources: Optional[Iterable[str]] = None,
    *,
    process_manager: Optional[ProxyProcessManager] = None,
    network_manager: Optional[ProxyNetworkManager] = None,
    requests_session: Optional[Any] = None,
    **options: Any,
) -> Proxy:
    return Proxy(
        process_manager=process_manager,
        network_manager=network_manager,
        proxies=proxies,
        sources=sources,
        requests_session=requests_session,
        **options,
    )
