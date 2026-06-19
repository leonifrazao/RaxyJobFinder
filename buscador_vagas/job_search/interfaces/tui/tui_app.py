from __future__ import annotations

import os
import threading

import pytermgui as ptg
from loguru import logger

from job_search.infrastructure.logging import resolve_error_log_path
from job_search.infrastructure.proxy.proxy_sources import DEFAULT_PROVIDER
from job_search.infrastructure.messaging.redis_search_event_subscriber import RedisSearchEventSubscriber
from job_search.interfaces.tui.tui_event_formatter import TuiEventFormatter
from job_search.interfaces.tui.tui_input_reader import TuiInputReader
from job_search.interfaces.tui.tui_search_runner import TuiSearchRunner
from job_search.interfaces.tui.tui_state import TuiState


TUI_CONFIG = """
config:
    Label:
        styles:
            value: dim bold
    InputField:
        styles:
            prompt: dim italic
            cursor: '@72'
    Window:
        styles:
            border: '60'
            corner: '60'
"""


class TuiApp:
    def __init__(self) -> None:
        self._reader = TuiInputReader()
        self._event_formatter = TuiEventFormatter()
        self._runner = TuiSearchRunner()
        self._events: list[str] = []
        self._event_label: ptg.Label | None = None
        self._search_started = False

    def run(self) -> int:
        self._search_started = False
        self._run_window()
        return 0

    def _run_window(self) -> None:
        with ptg.YamlLoader() as loader:
            loader.load(TUI_CONFIG)

        fields = self._build_fields(TuiState())
        with ptg.WindowManager() as manager:
            window = self._build_window(manager, fields)
            manager.add(window)

    def _build_fields(self, state: TuiState) -> dict[str, ptg.InputField]:
        return {
            "portal": ptg.InputField(state.portal, prompt="Portal: "),
            "keywords": ptg.InputField(state.keywords, prompt="Keywords: "),
            "location": ptg.InputField(state.location, prompt="Location: "),
            "provider": ptg.InputField(DEFAULT_PROVIDER, prompt="Provider: "),
            "valid_count": ptg.InputField(str(state.valid_count), prompt="Valid proxies: "),
            "max_count": ptg.InputField(str(state.max_count), prompt="Max proxy configs: "),
            "threads": ptg.InputField(str(state.threads), prompt="Proxy threads: "),
            "timeout": ptg.InputField(str(state.timeout), prompt="Timeout: "),
            "detail_timeout": ptg.InputField(str(state.detail_timeout), prompt="Detail timeout: "),
            "max_jobs": ptg.InputField(str(state.max_jobs), prompt="Max jobs: "),
            "details_limit": ptg.InputField(str(state.details_limit), prompt="Details limit: "),
            "detail_threads": ptg.InputField(str(state.detail_threads), prompt="Detail threads: "),
            "show_jobs": ptg.InputField(str(state.show_jobs), prompt="Show jobs: "),
            "jobs_output": ptg.InputField(state.jobs_output, prompt="Jobs JSON: "),
            "details_output": ptg.InputField(state.details_output, prompt="Details JSON: "),
            "redis_url": ptg.InputField(state.redis_url, prompt="Redis URL: "),
            "events_channel": ptg.InputField(state.events_channel, prompt="Redis channel: "),
        }

    def _build_window(self, manager: ptg.WindowManager, fields: dict[str, ptg.InputField]) -> ptg.Window:
        self._event_label = ptg.Label("[dim]Eventos em tempo real aparecem aqui apos Buscar.[/]")
        window = ptg.Window(
            "[bold 75]Raxy Job Finder[/]",
            "[dim]TUI experimental com backend SDK + Redis Pub/Sub. CLI segue disponivel com argumentos.[/]",
            "",
            ptg.Container(
                fields["portal"],
                fields["keywords"],
                fields["location"],
                fields["provider"],
                box="EMPTY_VERTICAL",
            ),
            "",
            ptg.Container(
                fields["valid_count"],
                fields["max_count"],
                fields["threads"],
                fields["timeout"],
                fields["detail_timeout"],
                fields["max_jobs"],
                fields["details_limit"],
                fields["detail_threads"],
                fields["show_jobs"],
                box="EMPTY_VERTICAL",
            ),
            "",
            ptg.Container(
                fields["jobs_output"],
                fields["details_output"],
                box="EMPTY_VERTICAL",
            ),
            "",
            ptg.Container(
                fields["redis_url"],
                fields["events_channel"],
                box="EMPTY_VERTICAL",
            ),
            "",
            ptg.Container(
                "[bold]Eventos[/]",
                self._event_label,
                box="EMPTY_VERTICAL",
            ),
            "",
            ["Buscar", lambda *_: self._submit(manager, fields)],
            ["CLI help", lambda *_: self._show_help(manager)],
            ["Sair", lambda *_: manager.stop()],
            width=78,
            box="DOUBLE",
        )
        return window.set_title("[210 bold]Raxy TUI").center()

    def _submit(self, manager: ptg.WindowManager, fields: dict[str, ptg.InputField]) -> None:
        if self._search_started:
            self._append_event("[WARN] Busca ja esta em andamento")
            return
        try:
            state = self._reader.read(fields)
        except ValueError as exc:
            self._show_error(manager, f"Valor numerico invalido: {exc}")
            return
        self._search_started = True
        os.environ["RAXY_REDIS_URL"] = state.redis_url
        os.environ["RAXY_REDIS_CHANNEL"] = state.events_channel
        self._append_event(f"[INFO] Iniciando backend SDK no canal {state.events_channel}")
        self._start_event_listener(state)
        self._start_search(manager, state)

    def _start_event_listener(self, state: TuiState) -> None:
        stop_event = threading.Event()
        subscriber = RedisSearchEventSubscriber(redis_url=state.redis_url, channel=state.events_channel)

        def handle(event: dict) -> None:
            self._append_event(self._event_formatter.format(event))

        thread = threading.Thread(target=subscriber.listen, args=(stop_event, handle), daemon=True)
        thread.start()

    def _start_search(self, manager: ptg.WindowManager, state: TuiState) -> None:
        def run() -> None:
            try:
                exit_code = self._runner.run(state)
                self._append_event(f"[INFO] Backend finalizado com codigo {exit_code}")
            except Exception as exc:
                logger.bind(component="tui", error=str(exc)).exception("tui_backend_failed")
                self._append_event(f"[ERROR] Backend falhou: {exc}")
                self._append_event(f"[ERROR] Log salvo em {resolve_error_log_path()}")

        threading.Thread(target=run, daemon=True).start()

    def _append_event(self, line: str) -> None:
        self._events.append(line)
        self._events = self._events[-12:]
        if self._event_label is not None:
            self._event_label.value = "\n".join(self._events)

    def _show_help(self, manager: ptg.WindowManager) -> None:
        manager.add(
            ptg.Window(
                "[bold]Uso CLI preservado[/]",
                "python buscador_vagas/buscador.py --portal linkedin --keywords Python",
                "",
                "Sem argumentos, este launcher abre a TUI experimental.",
                ["Fechar", lambda *_: manager.remove(manager.focused)],
                width=72,
                box="DOUBLE",
            ).center()
        )

    def _show_error(self, manager: ptg.WindowManager, message: str) -> None:
        manager.add(
            ptg.Window(
                "[red bold]Erro[/]",
                message,
                ["Fechar", lambda *_: manager.remove(manager.focused)],
                width=60,
                box="DOUBLE",
            ).center()
        )
