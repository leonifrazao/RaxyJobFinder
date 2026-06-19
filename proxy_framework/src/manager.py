from __future__ import annotations

import atexit
import os
import random
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

try:
    import urllib3 as _urllib3
except Exception:
    _urllib3 = None

try:
    import requests
except Exception:
    requests = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except Exception:
    Console = None
    Table = None
    Text = None

from .interfaces import ProxyNetworkManager, ProxyProcessManager, ProxyService
from .logging_utils import debug_log, get_logger
from .models import BridgeRuntime, Outbound, ProxyItem, ProxyTestResult
from .network import NetworkManager
from .parser import parse_uri_to_outbound
from .process import ProcessManager
from .storage import DEFAULT_CACHE_FILENAME, apply_cached_entry, format_timestamp, load_cache, make_base_entry, save_cache

__all__ = ["Proxy"]

logger = get_logger()


class Proxy(ProxyService):
    STATUS_STYLES: Dict[str, str] = {
        "AGUARDANDO": "dim",
        "TESTANDO": "yellow",
        "OK": "bold green",
        "ERRO": "bold red",
        "FILTRADO": "cyan",
    }

    Outbound = Outbound
    BridgeRuntime = BridgeRuntime

    def __init__(
        self,
        process_manager: Optional[ProxyProcessManager] = None,
        network_manager: Optional[ProxyNetworkManager] = None,
        proxies: Optional[Iterable[str]] = None,
        sources: Optional[Iterable[str]] = None,
        *,
        country: Optional[str] = None,
        base_port: int = 54000,
        max_count: int = 0,
        use_console: bool = False,
        use_cache: bool = True,
        cache_path: Optional[Union[str, os.PathLike[str]]] = None,
        command_output: bool = True,
        requests_session: Optional[Any] = None,
    ) -> None:
        self.country_filter = country
        self.base_port = base_port
        self.max_count = max_count
        self.requests = requests_session or requests
        self.use_console = bool(use_console and Console)
        self.console = Console() if self.use_console and Console else None

        self.process = process_manager or ProcessManager()
        self.network = network_manager or NetworkManager(self.requests, self.process)

        self._outbounds: List[Tuple[str, Outbound]] = []
        self._entries: List[ProxyItem] = []
        self._bridges: List[BridgeRuntime] = []
        self._running = False
        self._atexit_registered = False
        self._parse_errors: List[str] = []
        self.use_cache = use_cache
        default_cache_path = Path(__file__).with_name(DEFAULT_CACHE_FILENAME)
        self.cache_path = Path(cache_path) if cache_path is not None else default_cache_path
        self._cache_entries: Dict[str, ProxyTestResult] = {}
        self._stop_event = threading.Event()
        self._wait_thread: Optional[threading.Thread] = None
        self.command_output = bool(command_output)
        self._cache_available = False

        if self.use_cache:
            self._load_cache()
        if proxies:
            self.add_proxies(proxies)
        if sources:
            self.add_sources(sources)
        if self.use_cache and not self._entries and self._outbounds:
            self._prime_entries_from_cache()

        self.process.which_xray()

    @property
    def entries(self) -> List[ProxyItem]:
        return self._entries

    @property
    def parse_errors(self) -> List[str]:
        return list(self._parse_errors)

    def _register_new_outbound(self, raw_uri: str, outbound: Outbound) -> None:
        index = len(self._outbounds)
        entry = make_base_entry(index, raw_uri, outbound)
        if self.use_cache and self._cache_entries:
            cached = self._cache_entries.get(raw_uri)
            if cached:
                entry = apply_cached_entry(entry, cached)
                match = self.matches_country(entry, self.country_filter)
                entry = replace(entry, result=replace(entry.result, country_match=match))
        self._entries.append(entry)

    def _prime_entries_from_cache(self) -> None:
        if not self.use_cache or not self._cache_entries:
            return
        rebuilt: List[ProxyItem] = []
        for idx, (raw_uri, outbound) in enumerate(self._outbounds):
            entry = make_base_entry(idx, raw_uri, outbound)
            cached = self._cache_entries.get(raw_uri)
            if cached:
                entry = apply_cached_entry(entry, cached)
                match = self.matches_country(entry, self.country_filter)
                entry = replace(entry, result=replace(entry.result, country_match=match))
            rebuilt.append(entry)
        self._entries = rebuilt

    def _load_cache(self) -> None:
        if not self.use_cache:
            return
        self._cache_entries = load_cache(self.cache_path)
        self._cache_available = bool(self._cache_entries)

    def _save_cache(self, entries: List[ProxyItem]) -> None:
        if self.use_cache:
            save_cache(self.cache_path, entries)

    @staticmethod
    def _format_destination(host: Optional[str], port: Optional[int]) -> str:
        if not host or host == "-":
            return "-"
        if port is None:
            return host
        return f"{host}:{port}"

    @staticmethod
    def _check_country_match(country_info: Dict[str, Any], desired: Optional[str]) -> bool:
        if not desired:
            return True
        desired_norm = desired.strip().casefold()
        if not desired_norm:
            return True
        candidates = [
            str(country_info.get(k) or "").strip()
            for k in ("country", "country_code", "country_name")
            if country_info.get(k)
        ]
        candidates = [candidate for candidate in candidates if candidate and candidate != "-"]
        if not candidates:
            return False
        if any(candidate.casefold() == desired_norm for candidate in candidates):
            return True
        return any(desired_norm in candidate.casefold() or candidate.casefold() in desired_norm for candidate in candidates)

    @classmethod
    def matches_country(cls, entry: ProxyItem, desired: Optional[str]) -> bool:
        if not desired:
            return True
        exit_country_info = {"country": entry.result.proxy_country, "country_code": entry.result.proxy_country_code}
        server_country_info = {
            "country": entry.result.country,
            "country_code": entry.result.country_code,
            "country_name": entry.result.country_name,
        }
        effective_exit_info = exit_country_info if exit_country_info.get("country") else server_country_info
        if not cls._check_country_match(effective_exit_info, desired):
            return False
        if entry.result.proxy_ip and entry.result.proxy_ip != entry.result.ip:
            if not cls._check_country_match(server_country_info, desired):
                return False
        return True

    def add_proxies(self, proxies: Iterable[str]) -> int:
        added = 0
        for raw in proxies:
            if raw is None:
                continue
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                outbound = parse_uri_to_outbound(line)
            except Exception as exc:
                self._parse_errors.append(f"Linha ignorada: {line[:80]} -> {exc}")
                continue
            self._outbounds.append((line, outbound))
            self._register_new_outbound(line, outbound)
            added += 1
            if self.max_count and len(self._outbounds) >= self.max_count:
                break
        return added

    def add_sources(self, sources: Iterable[str]) -> int:
        added = 0
        for src in sources:
            text = self.network.read_source_text(src)
            added += self.add_proxies(ln.strip() for ln in text.splitlines())
        return added

    def _perform_health_checks(
        self,
        outbounds: List[Tuple[str, Outbound]],
        *,
        country_filter: Optional[str] = None,
        emit_progress: Optional[Any] = None,
        force_refresh: bool = False,
        functional_timeout: float = 10.0,
        test_url: str = "http://httpbin.org/ip",
        threads: Optional[int] = 1,
        stop_on_success: Optional[int] = None,
        stop_on_unique_success: bool = False,
    ) -> List[ProxyItem]:
        all_results: List[ProxyItem] = []
        reuse_cache = self.use_cache and not force_refresh
        success_count = 0
        unique_success_ips: set[str] = set()
        to_test: List[Tuple[int, str, Outbound]] = []

        def success_ip(entry: ProxyItem) -> Optional[str]:
            return entry.result.proxy_ip or entry.result.external_ip or entry.result.ip

        def register_success(entry: ProxyItem) -> bool:
            nonlocal success_count
            if entry.result.status != "OK":
                return False
            if not stop_on_unique_success:
                success_count += 1
                return True
            ip_key = success_ip(entry)
            if not ip_key:
                entry.result.status = "FILTRADO"
                entry.result.error = "Proxy funcional sem IP de saida identificavel"
                return False
            if ip_key in unique_success_ips:
                entry.result.status = "FILTRADO"
                entry.result.error = f"IP de saida duplicado: {ip_key}"
                return False
            unique_success_ips.add(ip_key)
            success_count += 1
            return True

        for idx, (raw, outbound) in enumerate(outbounds):
            base_entry = make_base_entry(idx, raw, outbound)
            if reuse_cache and raw in self._cache_entries:
                entry = apply_cached_entry(base_entry, self._cache_entries[raw])
                if country_filter and entry.result.status == "OK":
                    match = self.matches_country(entry, country_filter)
                    entry.result.country_match = match
                    if not match:
                        entry.result.status = "FILTRADO"
                        exit_country = entry.result.proxy_country or entry.result.country or "-"
                        entry.result.error = f"Filtro '{country_filter}': pais de saida e {exit_country}"
                all_results.append(entry)
                register_success(entry)
                if emit_progress:
                    self._emit_test_progress(entry, len(all_results), len(outbounds), emit_progress)
            else:
                to_test.append((idx, raw, outbound))

        limit_reached = stop_on_success is not None and stop_on_success > 0
        if limit_reached and success_count >= stop_on_success:
            for idx, raw, outbound in to_test:
                all_results.append(make_base_entry(idx, raw, outbound))
            all_results.sort(key=lambda x: x.index)
            return all_results

        def worker(idx: int, raw: str, outbound: Outbound) -> ProxyItem:
            entry = make_base_entry(idx, raw, outbound)
            try:
                entry.host, entry.port = self.network.outbound_host_port(outbound)
            except Exception:
                pass
            entry.result.status = "TESTANDO"
            result = self.network.test_outbound(raw, outbound, timeout=functional_timeout, test_url=test_url)
            finished_at = time.time()
            entry.host = result.get("host") or entry.host
            if result.get("port") is not None:
                entry.port = result.get("port")
            res = entry.result
            res.ip = result.get("ip") or res.ip
            res.country = result.get("country") or res.country
            res.country_code = result.get("country_code") or res.country_code
            res.country_name = result.get("country_name") or res.country_name
            res.ping_ms = result.get("ping_ms")
            res.tested_at_ts = finished_at
            res.tested_at = format_timestamp(finished_at)
            res.functional = result.get("functional", False)
            res.external_ip = result.get("external_ip")
            res.proxy_ip = result.get("proxy_ip")
            res.proxy_country = result.get("proxy_country")
            res.proxy_country_code = result.get("proxy_country_code")
            if res.functional:
                res.status = "OK"
                res.error = None
            else:
                res.status = "ERRO"
                res.error = result.get("error", "Teste falhou")
            if country_filter and res.status == "OK":
                res.country_match = self.matches_country(entry, country_filter)
                if not res.country_match:
                    res.status = "FILTRADO"
                    exit_country = res.proxy_country or res.country or "-"
                    res.error = f"Filtro '{country_filter}': pais de saida e {exit_country}"
            return entry

        if to_test:
            max_workers = threads if threads and threads > 0 else 1
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(worker, idx, raw, outbound) for idx, raw, outbound in to_test}
                tested_indices = set()
                for future in as_completed(futures):
                    try:
                        result_entry = future.result()
                    except Exception as exc:
                        logger.exception("Erro fatal em teste de proxy: %s", exc)
                        continue
                    all_results.append(result_entry)
                    tested_indices.add(result_entry.index)
                    register_success(result_entry)
                    if emit_progress:
                        self._emit_test_progress(result_entry, len(all_results), len(outbounds), emit_progress)
                    if limit_reached and success_count >= stop_on_success:
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        break
                for idx, raw, outbound in to_test:
                    if idx not in tested_indices:
                        all_results.append(make_base_entry(idx, raw, outbound))

        all_results.sort(key=lambda x: x.index)
        return all_results

    def _emit_test_progress(self, entry: ProxyItem, count: int, total: int, emit_progress: Any) -> None:
        destino = self._format_destination(entry.host, entry.port)
        ping = entry.result.ping_ms
        ping_fmt = f"{ping:.1f} ms" if isinstance(ping, (int, float)) else "-"
        status_fmt = {
            "OK": "[bold green]OK[/]",
            "ERRO": "[bold red]ERRO[/]",
            "TESTANDO": "[yellow]TESTANDO[/]",
            "AGUARDANDO": "[dim]AGUARDANDO[/]",
            "FILTRADO": "[cyan]FILTRADO[/]",
        }.get(entry.result.status, entry.result.status)
        cache_note = " [dim](cache)[/]" if entry.result.cached and Console else ""
        display_country = entry.result.proxy_country or entry.result.country or "-"
        emit_progress.print(
            f"[{count}/{total}] {status_fmt}{cache_note} [bold]{entry.tag}[/] -> "
            f"{destino} | IP: {entry.result.ip or '-'} | Pais: {display_country} | Ping: {ping_fmt}"
        )
        if entry.result.error:
            emit_progress.print(f"    [dim]Motivo: {entry.result.error}[/]")

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
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para testar.")
        country_filter = country if country is not None else self.country_filter
        emit = self.console if (self.console is not None and (verbose is None or verbose)) else None
        results = self._perform_health_checks(
            self._outbounds,
            country_filter=country_filter,
            emit_progress=emit,
            force_refresh=force,
            functional_timeout=timeout,
            test_url=test_url,
            threads=threads,
            stop_on_success=find_first,
            stop_on_unique_success=find_first_unique,
        )
        self._entries = results
        self.country_filter = country_filter
        self._save_cache(results)
        if self.console is not None and (verbose is None or verbose):
            self._render_test_summary(results, country_filter)
        return results

    def _render_test_summary(self, entries: List[ProxyItem], country_filter: Optional[str]) -> None:
        if not self.console or Table is None:
            return
        ok_entries = [e for e in entries if e.result.status == "OK"]
        table_entries = [entry for entry in ok_entries if entry.result.country_match] if country_filter else ok_entries
        self.console.print()
        self.console.rule("Proxies Funcionais")
        if table_entries:
            self.console.print(self._render_test_table(table_entries))
        else:
            self.console.print("[yellow]Nenhuma proxy funcional encontrada.[/yellow]")
        success = sum(1 for entry in entries if entry.result.status == "OK")
        fail = sum(1 for entry in entries if entry.result.status == "ERRO")
        filtered = sum(1 for entry in entries if entry.result.status == "FILTRADO")
        self.console.print()
        self.console.rule("Resumo do Teste")
        summary_parts = [f"[bold cyan]Total:[/] {len(entries)}", f"[bold green]Sucesso:[/] {success}", f"[bold red]Falhas:[/] {fail}"]
        if filtered:
            summary_parts.append(f"[cyan]Filtradas:[/] {filtered}")
        self.console.print("    ".join(summary_parts))

    @staticmethod
    def _render_test_table(entries: List[ProxyItem]) -> Any:
        if Table is None:
            raise RuntimeError("render_test_table requer rich.")
        entries.sort(key=lambda e: e.result.ping_ms or float("inf"))
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Tag", no_wrap=True, max_width=30)
        table.add_column("Destino", overflow="fold")
        table.add_column("IP Real", no_wrap=True)
        table.add_column("Pais", no_wrap=True)
        table.add_column("Ping", justify="right", no_wrap=True)
        for entry in entries:
            status = entry.result.status
            style = Proxy.STATUS_STYLES.get(status, "white")
            status_cell = Text(status, style=style) if Text else status
            ping = entry.result.ping_ms
            ping_str = f"{ping:.1f} ms" if isinstance(ping, (int, float)) else "-"
            table.add_row(
                status_cell,
                entry.tag or "-",
                Proxy._format_destination(entry.host, entry.port),
                entry.result.proxy_ip or entry.result.ip or "-",
                entry.result.proxy_country or entry.result.country or "-",
                ping_str,
            )
        return table

    @staticmethod
    def _wait_for_bridge_port(port: int, proc: Any, timeout: float = 3.0) -> None:
        deadline = time.time() + timeout
        last_error: Optional[Exception] = None
        while time.time() < deadline:
            if proc.poll() is not None:
                error_output = ""
                if proc.stderr:
                    try:
                        error_output = proc.stderr.read().decode("utf-8", errors="replace").strip()
                    except Exception:
                        error_output = ""
                raise RuntimeError(f"Bridge Xray finalizou antes de abrir a porta {port}. {error_output}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return
            except OSError as exc:
                last_error = exc
                time.sleep(0.1)
        raise RuntimeError(f"Bridge HTTP local nao abriu a porta {port} em {timeout:.1f}s: {last_error}")

    @debug_log(log_args=False, log_result=False, log_duration=True)
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
        if self._running:
            raise RuntimeError("As pontes ja estao em execucao. Chame stop() antes de iniciar novamente.")
        if not self._outbounds:
            raise RuntimeError("Nenhuma proxy carregada para iniciar.")

        country_filter = country if country is not None else self.country_filter
        if auto_test:
            self.test(threads=threads or 1, country=country_filter, verbose=self.use_console, find_first=find_first)
            country_filter = self.country_filter

        approved_entries = [
            entry for entry in self._entries
            if entry.result.status == "OK" and self.matches_country(entry, country_filter)
        ]
        approved_entries.sort(key=lambda entry: float(entry.result.ping_ms) if isinstance(entry.result.ping_ms, (int, float)) else float("inf"))

        if not approved_entries:
            if country_filter:
                raise RuntimeError(f"Nenhuma proxy aprovada para o pais '{country_filter}'.")
            raise RuntimeError("Nenhuma proxy aprovada para iniciar. Execute test() e verifique os resultados.")

        if amounts is not None:
            if not isinstance(amounts, int) or amounts <= 0:
                raise ValueError("amounts deve ser um inteiro positivo.")
            approved_entries = approved_entries[:amounts]

        xray_bin = self.process.which_xray()
        self._stop_event.clear()
        bridges_runtime: List[BridgeRuntime] = []

        try:
            for entry in approved_entries:
                raw_uri, outbound = self._outbounds[entry.index]
                port = self.process.find_available_port()
                cfg = self.process.make_xray_config_http_inbound(port, outbound)
                scheme = raw_uri.split("://", 1)[0].lower()
                proc, cfg_path = self.process.launch_bridge_with_diagnostics(xray_bin, cfg, outbound.tag)
                self._wait_for_bridge_port(port, proc)
                bridges_runtime.append(BridgeRuntime(
                    tag=outbound.tag,
                    port=port,
                    scheme=scheme,
                    uri=raw_uri,
                    process=proc,
                    workdir=cfg_path.parent,
                ))
        except Exception:
            for bridge in bridges_runtime:
                self.process.terminate_process(bridge.process)
                self.process.safe_remove_dir(bridge.workdir)
                self.process.release_port(bridge.port)
            raise

        self._bridges = bridges_runtime
        self._running = True
        if not self._atexit_registered:
            atexit.register(self.stop)
            self._atexit_registered = True

        active_proxies = [replace(entry, uri=bridge.url) for entry, bridge in zip(approved_entries, bridges_runtime)]
        if wait:
            self.wait()
        else:
            self._start_wait_thread()
        return active_proxies

    def _start_wait_thread(self) -> None:
        if self._wait_thread and self._wait_thread.is_alive():
            return
        self._wait_thread = threading.Thread(target=self._wait_loop_wrapper, name="ProxyWaitThread", daemon=True)
        self._wait_thread.start()

    def _wait_loop_wrapper(self) -> None:
        try:
            self.wait()
        except RuntimeError:
            pass

    def wait(self) -> None:
        if not self._running:
            raise RuntimeError("Nenhuma ponte ativa para aguardar.")
        try:
            while not self._stop_event.is_set():
                alive = any(bridge.process and bridge.process.poll() is None for bridge in self._bridges)
                if not alive:
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        if not self._running and not self._bridges:
            return
        self._stop_event.set()
        for bridge in list(self._bridges):
            self.process.terminate_process(bridge.process)
            self.process.safe_remove_dir(bridge.workdir)
            self.process.release_port(bridge.port)
        self._bridges = []
        self._running = False
        if self._wait_thread and self._wait_thread is not threading.current_thread():
            self._wait_thread.join(timeout=1.0)
        self._wait_thread = None

    def get_http_proxy(self) -> List[Dict[str, Any]]:
        if not self._running:
            return []
        return [{"id": idx, "url": bridge.url, "uri": bridge.uri} for idx, bridge in enumerate(self._bridges)]

    def rotate_proxy(self, bridge_id: int) -> bool:
        if not self._running or not (0 <= bridge_id < len(self._bridges)):
            return False

        bridge = self._bridges[bridge_id]
        uri_to_replace = bridge.uri
        entry_to_invalidate = next((entry for entry in self._entries if entry.uri == uri_to_replace), None)
        if entry_to_invalidate:
            entry_to_invalidate.result.status = "ERRO"
            entry_to_invalidate.result.error = "Proxy invalidada manualmente via rotacao"
            entry_to_invalidate.result.tested_at_ts = time.time()
            self._save_cache(self._entries)

        candidates = [
            entry for entry in self._entries
            if entry.result.status == "OK"
            and self.matches_country(entry, self.country_filter)
            and entry.uri != uri_to_replace
        ]
        if not candidates:
            return False

        new_entry = random.choice(candidates)
        new_raw_uri = new_entry.uri
        new_outbound = new_entry.outbound
        new_scheme = new_raw_uri.split("://", 1)[0].lower()
        self.process.terminate_process(bridge.process, wait_timeout=2)
        self.process.safe_remove_dir(bridge.workdir)

        try:
            xray_bin = self.process.which_xray()
            cfg = self.process.make_xray_config_http_inbound(bridge.port, new_outbound)
            new_proc, new_cfg_path = self.process.launch_bridge_with_diagnostics(xray_bin, cfg, new_outbound.tag)
        except Exception:
            bridge.process = None
            return False

        self._bridges[bridge_id] = BridgeRuntime(
            tag=new_outbound.tag,
            port=bridge.port,
            scheme=new_scheme,
            uri=new_raw_uri,
            process=new_proc,
            workdir=new_cfg_path.parent,
        )
        return True
