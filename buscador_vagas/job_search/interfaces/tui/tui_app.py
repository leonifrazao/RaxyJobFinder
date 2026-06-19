from __future__ import annotations

import pytermgui as ptg

from job_search.infrastructure.proxy.proxy_sources import DEFAULT_PROVIDER
from job_search.interfaces.cli.command import main as cli_main
from job_search.interfaces.tui.tui_argument_builder import TuiArgumentBuilder
from job_search.interfaces.tui.tui_input_reader import TuiInputReader
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
        self._argument_builder = TuiArgumentBuilder()
        self._selected_args: list[str] | None = None

    def run(self) -> int:
        self._selected_args = None
        self._run_window()
        if self._selected_args is None:
            return 0
        return cli_main(self._selected_args)

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
            "show_jobs": ptg.InputField(str(state.show_jobs), prompt="Show jobs: "),
            "jobs_output": ptg.InputField(state.jobs_output, prompt="Jobs JSON: "),
            "details_output": ptg.InputField(state.details_output, prompt="Details JSON: "),
        }

    def _build_window(self, manager: ptg.WindowManager, fields: dict[str, ptg.InputField]) -> ptg.Window:
        window = ptg.Window(
            "[bold 75]Raxy Job Finder[/]",
            "[dim]TUI experimental. A CLI continua disponivel com argumentos.[/]",
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
            ["Buscar", lambda *_: self._submit(manager, fields)],
            ["CLI help", lambda *_: self._show_help(manager)],
            ["Sair", lambda *_: manager.stop()],
            width=78,
            box="DOUBLE",
        )
        return window.set_title("[210 bold]Raxy TUI").center()

    def _submit(self, manager: ptg.WindowManager, fields: dict[str, ptg.InputField]) -> None:
        try:
            state = self._reader.read(fields)
        except ValueError as exc:
            self._show_error(manager, f"Valor numerico invalido: {exc}")
            return
        self._selected_args = self._argument_builder.build(state)
        manager.stop()

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
