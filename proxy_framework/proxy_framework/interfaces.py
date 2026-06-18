from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import Outbound, ProxyItem


class ProxyService(ABC):
    @abstractmethod
    def add_sources(self, sources: Iterable[str]) -> int:
        raise NotImplementedError

    @abstractmethod
    def add_proxies(self, proxies: Iterable[str]) -> int:
        raise NotImplementedError

    @abstractmethod
    def test(
        self,
        *,
        threads: Optional[int] = 1,
        country: Optional[str] = None,
        verbose: Optional[bool] = None,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip",
        force: bool = False,
        find_first: Optional[int] = None,
        find_first_unique: bool = False,
    ) -> List[ProxyItem]:
        raise NotImplementedError

    @abstractmethod
    def start(
        self,
        *,
        threads: Optional[int] = None,
        amounts: Optional[int] = None,
        country: Optional[str] = None,
        auto_test: bool = True,
        wait: bool = False,
        find_first: Optional[int] = None,
    ) -> List[ProxyItem]:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_http_proxy(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def rotate_proxy(self, bridge_id: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def wait(self) -> None:
        raise NotImplementedError


class ProxyProcessManager(ABC):
    @abstractmethod
    def which_xray(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def find_available_port(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def release_port(self, port: Optional[int]) -> None:
        raise NotImplementedError

    @abstractmethod
    def terminate_process(self, proc: Optional[subprocess.Popen], *, wait_timeout: float = 3.0) -> None:
        raise NotImplementedError

    @abstractmethod
    def safe_remove_dir(self, path: Optional[Path]) -> None:
        raise NotImplementedError

    @abstractmethod
    def make_xray_config_http_inbound(self, port: int, outbound: Outbound) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def launch_bridge_with_diagnostics(self, xray_bin: str, cfg: Dict[str, Any], name: str) -> Tuple[subprocess.Popen, Path]:
        raise NotImplementedError

    @abstractmethod
    def temporary_bridge(self, outbound: Outbound, *, tag_prefix: str = "temp") -> AbstractContextManager[Tuple[int, subprocess.Popen]]:
        raise NotImplementedError


class ProxyNetworkManager(ABC):
    @abstractmethod
    def read_source_text(self, source: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def outbound_host_port(self, outbound: Outbound) -> Tuple[str, int]:
        raise NotImplementedError

    @abstractmethod
    def test_outbound(
        self,
        raw_uri: str,
        outbound: Outbound,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip",
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def test_proxy_functionality(
        self,
        raw_uri: str,
        outbound: Outbound,
        timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip",
    ) -> Dict[str, Any]:
        raise NotImplementedError
