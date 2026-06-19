from __future__ import annotations

import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
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
        self._progress(progress_callback, "proxy_prepare_started", "Baixando lista de proxies...", {"provider": self.provider_name, "sources": len(sources)})

        self._proxy = create_proxy(
            sources=sources,
            max_count=max_count,
            use_cache=False,
            use_console=self.use_console,
        )
        try:
            self._progress(progress_callback, "proxy_testing", "Testando proxies...", {"threads": threads, "timeout": timeout})
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
                self._progress(progress_callback, "proxy_no_working", "Nenhuma proxy funcional encontrada!", {"total": len(results)})
                raise RuntimeError("Nenhuma proxy funcional encontrada para o portal.")

            self._progress(progress_callback, "proxy_tested", f"{len(working)} proxies OK, iniciando bridges...", {"working": len(working), "total": len(results)})
            active = self._proxy.start(amounts=valid_count, auto_test=False)

            self._progress(progress_callback, "proxy_verifying", f"Verificando {len(active)} bridges...", {"expected": len(active)})
            bridge_results: list[BridgeEndpoint | None] = [None] * len(active)

            def _verify_one(index: int, bridge_url: str) -> BridgeEndpoint | None:
                log.bind(bridge_index=index, bridge_url=bridge_url).debug("proxy_bridge_verifying")
                try:
                    resp = requests.get(
                        test_url,
                        proxies={"http": bridge_url, "https": bridge_url},
                        timeout=timeout,
                        verify=False,
                        headers={
                            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
                        },
                    )
                    resp.raise_for_status()
                    log.bind(bridge_index=index, status_code=resp.status_code).debug("proxy_bridge_verified")
                    return BridgeEndpoint(index=index, url=bridge_url)
                except Exception as exc:
                    log.bind(bridge_index=index, error=str(exc)).warning("proxy_bridge_verification_failed")
                    return None

            with ThreadPoolExecutor(max_workers=min(len(active), 10)) as executor:
                fut_map = {executor.submit(_verify_one, i, item.uri): i for i, item in enumerate(active)}
                for future in as_completed(fut_map):
                    i = fut_map[future]
                    result = future.result()
                    bridge_results[i] = result
                    if result is not None:
                        self._progress(progress_callback, "proxy_bridge_verified", f"Bridge {i+1}/{len(active)} OK", {"index": i, "total": len(active)})
                    else:
                        self._progress(progress_callback, "proxy_bridge_failed", f"Bridge {i+1}/{len(active)} falhou", {"index": i, "total": len(active)})

            verified_bridges = [b for b in bridge_results if b is not None]

            if not verified_bridges:
                log.error("proxy_prepare_no_verified_bridges")
                self._progress(progress_callback, "proxy_no_bridges", "Nenhuma bridge ativa apos verificacao!", {})
                raise RuntimeError(
                    "Nenhuma ponte proxy ativa: todas as bridges falharam na verificacao pos-inicializacao. "
                    "O Xray pode nao estar funcionando ou as portas estao bloqueadas."
                )

            bridges = verified_bridges
            log.bind(
                total_results=len(results),
                working_count=len(working),
                bridges_count=len(bridges),
                bridges_expected=len(active),
            ).info("proxy_prepare_finished")
            self._progress(progress_callback, "proxy_prepare_finished", f"{len(bridges)} bridges ativas", {"bridges": len(bridges)})
            return bridges
        except Exception:
            self._proxy.stop()
            raise

    def stop(self) -> None:
        if self._proxy is not None:
            logger.bind(component="proxy_pool", provider=self.provider_name).info("proxy_pool_stopping")
            self._proxy.stop()
            self._proxy = None

    @staticmethod
    def _progress(callback: Callable[[str, str, dict], None] | None, name: str, message: str, payload: dict) -> None:
        if callback:
            try:
                callback(name, message, payload)
            except Exception:
                pass
