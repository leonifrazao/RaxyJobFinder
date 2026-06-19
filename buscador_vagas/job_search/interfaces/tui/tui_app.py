from __future__ import annotations

import os
import threading

import pytermgui as ptg
from loguru import logger

from job_search.application.events import SearchEventName
from job_search.infrastructure.config import load_settings
from job_search.infrastructure.logging import resolve_error_log_path
from job_search.infrastructure.messaging.redis_search_event_subscriber import RedisSearchEventSubscriber
from job_search.interfaces.tui.tui_search_runner import TuiSearchRunner
from job_search.interfaces.tui.tui_state import TuiState


PENDING = "[dim]aguardando...[/]"
PROCESSING = "[yellow]processando...[/]"


class TuiApp:
    def __init__(self) -> None:
        self._reader = TuiInputReader()
        self._runner = TuiSearchRunner()
        self._search_started = False
        self._manager: ptg.WindowManager | None = None
        self._fields: dict[str, ptg.InputField] = {}
        self._proxy_label: ptg.Label | None = None
        self._search_label: ptg.Label | None = None
        self._detail_label: ptg.Label | None = None
        self._save_label: ptg.Label | None = None
        self._tui_cfg = load_settings().tui

    def run(self) -> int:
        self._search_started = False
        self._run_window()
        return 0

    def _run_window(self) -> None:
        with ptg.YamlLoader() as loader:
            loader.load(_build_ptg_config(self._tui_cfg))

        self._fields = self._build_fields(TuiState.from_config())
        with ptg.WindowManager() as manager:
            self._manager = manager
            window = self._build_window()
            manager.add(window)

    def _build_fields(self, state: TuiState) -> dict[str, ptg.InputField]:
        settings = load_settings()
        default_provider = settings.proxy.default_provider
        return {
            "portal": ptg.InputField(state.portal, prompt="Portal: "),
            "keywords": ptg.InputField(state.keywords, prompt="Keywords: "),
            "location": ptg.InputField(state.location, prompt="Location: "),
            "location_id": ptg.InputField(state.location_id, prompt="Loc ID: "),
            "location_choice": ptg.InputField(state.location_choice, prompt="Loc choice: "),
            "provider": ptg.InputField(default_provider, prompt="Provider: "),
            "valid_count": ptg.InputField(str(state.valid_count), prompt="Valid: "),
            "jobs_per_proxy": ptg.InputField(str(state.jobs_per_proxy), prompt="Jobs/proxy: "),
            "max_count": ptg.InputField(str(state.max_count), prompt="Max cfgs: "),
            "threads": ptg.InputField(str(state.threads), prompt="Threads: "),
            "timeout": ptg.InputField(str(state.timeout), prompt="Timeout: "),
            "detail_timeout": ptg.InputField(str(state.detail_timeout), prompt="Det timeout: "),
            "max_jobs": ptg.InputField(str(state.max_jobs), prompt="Max jobs: "),
            "start": ptg.InputField(str(state.start), prompt="Start: "),
            "details_limit": ptg.InputField(str(state.details_limit), prompt="Det limit: "),
            "detail_threads": ptg.InputField(str(state.detail_threads), prompt="Det threads: "),
            "show_jobs": ptg.InputField(str(state.show_jobs), prompt="Show: "),
            "gd_cookie": ptg.InputField(state.gd_cookie, prompt="GD cookie: "),
            "filters_path": ptg.InputField(state.filters_path, prompt="Filters: "),
            "jobs_output": ptg.InputField(state.jobs_output, prompt="Jobs out: "),
            "details_output": ptg.InputField(state.details_output, prompt="Details out: "),
            "redis_url": ptg.InputField(state.redis_url, prompt="Redis: "),
            "events_channel": ptg.InputField(state.events_channel, prompt="Channel: "),
        }

    def _reset_fields(self) -> None:
        defaults = TuiState.from_config()
        for key, default_field in self._build_fields(defaults).items():
            if key in self._fields:
                self._fields[key].value = default_field.value

    def _reset_status(self) -> None:
        if self._proxy_label is not None:
            self._proxy_label.value = f"proxy:    {PENDING}"
        if self._search_label is not None:
            self._search_label.value = f"busca:    {PENDING}"
        if self._detail_label is not None:
            self._detail_label.value = f"detalhes: {PENDING}"
        if self._save_label is not None:
            self._save_label.value = f"salvar:   {PENDING}"

    def _build_window(self) -> ptg.Window:
        self._proxy_label = ptg.Label(f"proxy:    {PENDING}")
        self._search_label = ptg.Label(f"busca:    {PENDING}")
        self._detail_label = ptg.Label(f"detalhes: {PENDING}")
        self._save_label = ptg.Label(f"salvar:   {PENDING}")
        f = self._fields
        window = ptg.Window(
            "[bold 75]Raxy Job Finder[/]",
            "[dim]TUI — preencha e clique Buscar[/]",
            "",
            _section("BUSCA"),
            f["portal"], f["keywords"], f["location"],
            f["location_id"], f["location_choice"],
            "",
            _section("PROXY"),
            f["provider"], f["valid_count"],
            f["jobs_per_proxy"], f["max_count"],
            f["threads"], f["timeout"],
            "",
            _section("DETALHES / PAGINACAO"),
            f["detail_timeout"], f["detail_threads"],
            f["details_limit"], f["max_jobs"],
            f["start"], f["show_jobs"],
            "",
            _section("GLASSDOOR / FILTROS"),
            f["gd_cookie"], f["filters_path"],
            "",
            _section("SAIDA / REDIS"),
            f["jobs_output"], f["details_output"],
            f["redis_url"], f["events_channel"],
            "",
            _section("STATUS"),
            self._proxy_label,
            self._search_label,
            self._detail_label,
            self._save_label,
            "",
            ["Buscar", lambda *_: self._submit()],
            ["Limpar campos", lambda *_: self._reset_fields()],
            ["Ajuda CLI", lambda *_: self._show_help()],
            ["Sair", lambda *_: self._manager.stop() if self._manager else None],
            width=self._tui_cfg.window_width,
            box=self._tui_cfg.window_box,
        )
        return window.set_title(self._tui_cfg.window_title).center()

    def _submit(self) -> None:
        if self._search_started:
            return
        try:
            state = self._reader.read(self._fields)
        except ValueError as exc:
            self._show_error(f"Valor numerico invalido: {exc}")
            return
        self._search_started = True
        self._reset_status()
        os.environ["RAXY_REDIS_URL"] = state.redis_url
        os.environ["RAXY_REDIS_CHANNEL"] = state.events_channel
        self._set_proxy(PROCESSING)
        self._set_search(PENDING)
        self._set_detail(PENDING)
        self._set_save(PENDING)
        self._start_event_listener(state)
        self._start_search(state)

    def _start_event_listener(self, state: TuiState) -> None:
        stop_event = threading.Event()
        subscriber = RedisSearchEventSubscriber(redis_url=state.redis_url, channel=state.events_channel)

        def handle(event: dict) -> None:
            self._handle_event(event)

        thread = threading.Thread(target=subscriber.listen, args=(stop_event, handle), daemon=True)
        thread.start()

    def _start_search(self, state: TuiState) -> None:
        def run() -> None:
            try:
                exit_code = self._runner.run(state)
                self._search_started = False
            except Exception as exc:
                logger.bind(component="tui", error=str(exc)).exception("tui_backend_failed")
                self._set_proxy("[red]falha[/]")
                self._set_search("[red]falha[/]")
                self._set_detail("[red]falha[/]")
                self._set_save("[red]falha[/]")

        threading.Thread(target=run, daemon=True).start()

    def _handle_event(self, event: dict) -> None:
        name = str(event.get("name", ""))
        message = str(event.get("message", ""))
        payload = event.get("payload") or {}
        error = payload.get("error") or ""

        if name.startswith("proxy_"):
            if name == SearchEventName.PROXY_PREPARE_STARTED.value:
                self._set_proxy("[yellow]baixando proxies...[/]")
            elif name == SearchEventName.PROXY_TESTING.value:
                self._set_proxy("[yellow]testando proxies...[/]")
            elif name == SearchEventName.PROXY_TESTED.value:
                w = payload.get("working", 0)
                t = payload.get("total", 0)
                self._set_proxy(f"[green]{w}/{t} OK[/], [yellow]iniciando bridges...[/]")
            elif name == SearchEventName.PROXY_VERIFYING.value:
                self._set_proxy(f"[yellow]verificando bridges...[/]")
            elif name == SearchEventName.PROXY_BRIDGE_VERIFIED.value:
                idx = payload.get("index", 0)
                total = payload.get("total", 0)
                self._set_proxy(f"[green]bridge {idx}/{total} OK[/]")
            elif name == SearchEventName.PROXY_BRIDGE_FAILED.value:
                idx = payload.get("index", 0)
                total = payload.get("total", 0)
                self._set_proxy(f"[red]bridge {idx}/{total} falhou[/]")
            elif name == SearchEventName.PROXY_NO_WORKING.value:
                self._set_proxy("[red]nenhuma proxy funcional![/]")
            elif name == SearchEventName.PROXY_PREPARE_FINISHED.value:
                bridges = payload.get("bridges", 0)
                self._set_proxy(f"[green]{bridges} bridges ativas[/]")

        elif name.startswith("search_"):
            if name == SearchEventName.SEARCH_BRIDGE_ATTEMPT.value:
                self._set_search("[yellow]buscando vagas...[/]")
            elif name == SearchEventName.SEARCH_BRIDGE_SUCCEEDED.value:
                jobs = payload.get("jobs_count", 0)
                status = payload.get("status_code", 0)
                self._set_search(f"[green]{jobs} vagas encontradas[/] (HTTP {status})")
            elif name == SearchEventName.SEARCH_BRIDGE_FAILED.value:
                self._set_search(f"[red]falha na busca[/]")

        elif name == SearchEventName.DETAIL_STARTED.value:
            total = payload.get("total", 0)
            self._set_detail(f"[yellow]detalhando 0/{total}...[/]")
            self._detail_total = total
        elif name == SearchEventName.DETAIL_PROGRESS.value:
            done = payload.get("done", 0)
            total = payload.get("total", 0)
            ok = payload.get("ok", 0)
            self._set_detail(f"[yellow]{done}/{total}[/] ([green]{ok} OK[/])")
        elif name == SearchEventName.DETAIL_FAILED.value:
            self._set_detail(f"[red]{message}[/]")

        elif name == SearchEventName.SAVE_STARTED.value:
            self._set_save("[yellow]salvando vagas...[/]")
        elif name == SearchEventName.SAVE_DETAILS_STARTED.value:
            self._set_save("[yellow]salvando detalhes...[/]")
        elif name == SearchEventName.SAVE_FINISHED.value:
            self._set_save("[green]resultados salvos[/]")

        elif name == SearchEventName.JOB_SEARCH_FINISHED.value:
            jobs = payload.get("jobs_detailed", 0)
            self._set_detail(f"[green]{jobs} vagas detalhadas[/]")

    def _set_proxy(self, value: str) -> None:
        if self._proxy_label is not None:
            self._proxy_label.value = f"proxy:    {value}"

    def _set_search(self, value: str) -> None:
        if self._search_label is not None:
            self._search_label.value = f"busca:    {value}"

    def _set_detail(self, value: str) -> None:
        if self._detail_label is not None:
            self._detail_label.value = f"detalhes: {value}"

    def _set_save(self, value: str) -> None:
        if self._save_label is not None:
            self._save_label.value = f"salvar:   {value}"

    def _show_help(self) -> None:
        if not self._manager:
            return
        self._manager.add(
            ptg.Window(
                "[bold]Uso CLI preservado[/]",
                "python buscador_vagas/buscador.py --portal linkedin --keywords Python",
                "",
                "Todos os parametros da TUI estao disponiveis como argumentos CLI:",
                "  --portal, --keywords, --location, --provider, --valid-count",
                "  --jobs-per-proxy, --max-count, --threads, --timeout,",
                "  --detail-timeout, --details-limit, --detail-threads,",
                "  --max-jobs, --start, --show-jobs, --gd-cookie, --filters",
                "  --jobs-output, --details-output",
                "",
                "Exemplo completo:",
                "  python buscador_vagas/buscador.py \\",
                "    --portal linkedin --keywords Python --location Brasil \\",
                "    --valid-count 25 --timeout 15 --detail-timeout 15",
                "",
                "Portais disponiveis: linkedin, gupy, glassdoor",
                "Providers: veja job_search/infrastructure/proxy/proxy_sources.py",
                "",
                ["Fechar", lambda *_: self._manager.remove(self._manager.focused) if self._manager else None],
                width=self._tui_cfg.help_window_width,
                box=self._tui_cfg.window_box,
            ).center()
        )

    def _show_error(self, message: str) -> None:
        if not self._manager:
            return
        self._manager.add(
            ptg.Window(
                "[red bold]Erro[/]",
                message,
                ["Fechar", lambda *_: self._manager.remove(self._manager.focused) if self._manager else None],
                width=self._tui_cfg.error_window_width,
                box=self._tui_cfg.window_box,
            ).center()
        )


def _section(title: str) -> ptg.Label:
    return ptg.Label(f"[bold 210]{title}[/]")


class TuiInputReader:
    def read(self, fields: dict[str, ptg.InputField]) -> TuiState:
        return TuiState(
            portal=_text(fields["portal"]),
            keywords=_text(fields["keywords"]),
            location=_text(fields["location"]),
            location_id=_text(fields["location_id"]),
            location_choice=_text(fields["location_choice"]),
            provider=_text(fields["provider"]),
            valid_count=_int(fields["valid_count"]),
            jobs_per_proxy=_int(fields["jobs_per_proxy"]),
            max_count=_int(fields["max_count"]),
            threads=_int(fields["threads"]),
            timeout=_float(fields["timeout"]),
            detail_timeout=_float(fields["detail_timeout"]),
            max_jobs=_int(fields["max_jobs"]),
            start=_int(fields["start"]),
            details_limit=_int(fields["details_limit"]),
            detail_threads=_int(fields["detail_threads"]),
            show_jobs=_int(fields["show_jobs"]),
            gd_cookie=_text(fields["gd_cookie"]),
            filters_path=_text(fields["filters_path"]),
            jobs_output=_text(fields["jobs_output"]),
            details_output=_text(fields["details_output"]),
            redis_url=_text(fields["redis_url"]),
            events_channel=_text(fields["events_channel"]),
        )


def _text(field: ptg.InputField) -> str:
    return str(field.value).strip()


def _int(field: ptg.InputField) -> int:
    raw = _text(field)
    return int(raw) if raw else 0


def _float(field: ptg.InputField) -> float:
    raw = _text(field)
    return float(raw) if raw else 0.0


def _build_ptg_config(tui_cfg) -> str:
    import yaml
    return yaml.safe_dump(tui_cfg.pytermgui_config.value, default_flow_style=False)
