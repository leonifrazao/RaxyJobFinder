from __future__ import annotations

import os
import threading
from pathlib import Path
from collections.abc import Callable, Sequence

from loguru import logger
from prompt_toolkit import print_formatted_text
from prompt_toolkit.shortcuts import input_dialog, message_dialog, radiolist_dialog, yes_no_dialog

from job_search.application.ports import SearchEventSubscriber
from job_search.infrastructure.config import find_config_path, load_settings
from job_search.infrastructure.messaging.redis_search_event_subscriber import RedisSearchEventSubscriber
from job_search.interfaces.tui.tui_event_formatter import TuiEventFormatter
from job_search.interfaces.tui.tui_prompter import Choice, TuiPrompter
from job_search.interfaces.tui.tui_search_runner import TuiSearchRunner
from job_search.interfaces.tui.tui_state import TuiState
from job_search.interfaces.tui.tui_view import TuiJobSearchView


SubscriberFactory = Callable[[str, str], SearchEventSubscriber]


class PromptToolkitPrompter:
    def select(self, title: str, text: str, values: Sequence[Choice], default: str) -> str | None:
        ordered_values = _default_first(values, default)
        return radiolist_dialog(title=title, text=text, values=list(ordered_values)).run()

    def text(self, title: str, text: str, default: str = "") -> str | None:
        return input_dialog(title=title, text=text, default=default).run()

    def confirm(self, title: str, text: str, default: bool = False) -> bool | None:
        result = yes_no_dialog(title=title, text=text).run()
        return default if result is None else result

    def message(self, title: str, text: str) -> None:
        message_dialog(title=title, text=text).run()


class TuiApp:
    def __init__(
        self,
        runner: TuiSearchRunner | None = None,
        subscriber_factory: SubscriberFactory | None = None,
        prompter: TuiPrompter | None = None,
        event_printer: Callable[[str], None] | None = None,
        config_path: str | Path = "config.yaml",
    ) -> None:
        self._prompter = prompter or PromptToolkitPrompter()
        view = TuiJobSearchView(self._prompter)
        self._runner = runner or TuiSearchRunner(view=view)
        self._subscriber_factory = subscriber_factory or self._build_subscriber
        self._formatter = TuiEventFormatter()
        self._event_printer = event_printer or print_formatted_text
        self._event_stop_event: threading.Event | None = None
        self._event_thread: threading.Thread | None = None
        self._event_lines: list[str] = []
        self._config_path = Path(config_path)

    def run(self) -> int:
        config_path = find_config_path(str(self._config_path))
        if config_path is None:
            self._prompter.message(
                "Config obrigatorio",
                f"Crie um arquivo {self._config_path} antes de abrir a TUI.",
            )
            return 1

        load_settings(str(config_path), reload=True)
        state = self._prompt_state(TuiState.from_config())
        if state is None:
            return 0

        os.environ["RAXY_REDIS_URL"] = state.redis_url
        os.environ["RAXY_REDIS_CHANNEL"] = state.events_channel
        self._start_event_listener(state)
        try:
            result = self._runner.run(state)
            self._prompter.message(
                "Busca finalizada",
                f"Resultados salvos em:\n{state.jobs_output}\n{state.details_output}",
            )
            return result
        except Exception as exc:
            logger.bind(component="tui", error=str(exc)).exception("tui_backend_failed")
            self._prompter.message("Erro na busca", str(exc))
            return 1
        finally:
            self._stop_event_listener()

    @staticmethod
    def _build_subscriber(redis_url: str, channel: str) -> SearchEventSubscriber:
        return RedisSearchEventSubscriber(redis_url=redis_url, channel=channel)

    def _prompt_state(self, defaults: TuiState) -> TuiState | None:
        settings = load_settings()
        portal = self._prompter.select(
            "Portal",
            "Escolha o portal de vagas.",
            [(portal, portal) for portal in settings.portals],
            defaults.portal,
        )
        if portal is None:
            return None

        work_type = "normal"
        under_10_applicants = False
        recent_period = "any"
        if portal == "linkedin":
            selected_work_type = self._prompter.select(
                "Modelo de trabalho",
                "Filtro de modalidade do LinkedIn.",
                [
                    ("normal", "Normal/presencial"),
                    ("remote", "Remoto"),
                    ("hybrid", "Hibrido"),
                ],
                defaults.work_type,
            )
            if selected_work_type is None:
                return None
            work_type = selected_work_type
            under_10 = self._prompter.confirm(
                "Menos de 10 candidaturas",
                "Filtrar vagas do LinkedIn com menos de 10 candidaturas?",
                defaults.under_10_applicants,
            )
            if under_10 is None:
                return None
            under_10_applicants = under_10
            selected_recent_period = self._prompter.select(
                "Vagas recentes",
                "Periodo de publicacao no LinkedIn.",
                [
                    ("any", "Qualquer periodo"),
                    ("day", "Ultimas 24h"),
                    ("week", "Ultima semana"),
                    ("month", "Ultimo mes"),
                ],
                defaults.recent_period,
            )
            if selected_recent_period is None:
                return None
            recent_period = selected_recent_period

        filter_by_keywords = self._prompter.confirm(
            "Filtro por keyword",
            "Filtrar vagas que contenham a keyword no titulo ou descricao?",
            defaults.filter_by_keywords,
        )
        if filter_by_keywords is None:
            return None

        output_cfg = settings.output
        jobs_output = output_cfg.jobs_path.format(portal=portal)
        details_output = output_cfg.details_path.format(portal=portal)

        try:
            return TuiState(
                portal=portal,
                keywords=self._prompt_text("Keywords", "Termo de busca", defaults.keywords),
                location=self._prompt_text("Localizacao", "Texto de localizacao", defaults.location),
                location_id="",
                location_choice="",
                max_jobs=self._prompt_int("Vagas", "Quantas vagas voce quer?", defaults.max_jobs),
                work_type=work_type,
                under_10_applicants=under_10_applicants,
                recent_period=recent_period,
                provider=defaults.provider,
                valid_count=defaults.valid_count,
                jobs_per_proxy=defaults.jobs_per_proxy,
                max_count=defaults.max_count,
                threads=defaults.threads,
                timeout=defaults.timeout,
                detail_timeout=defaults.detail_timeout,
                start=defaults.start,
                detail_threads=defaults.detail_threads,
                show_jobs=defaults.show_jobs,
                gd_cookie=self._prompt_text("Glassdoor cookie", "Cookie do Glassdoor", defaults.gd_cookie) if portal == "glassdoor" else "",
                filters_path=self._prompt_text("Filtro JSON", "Caminho do filtro JSON (opcional)", defaults.filters_path),
                filter_by_keywords=filter_by_keywords,
                jobs_output=jobs_output,
                details_output=details_output,
                redis_url=defaults.redis_url,
                events_channel=defaults.events_channel,
            )
        except ValueError as exc:
            self._prompter.message("Valor invalido", str(exc))
            return None

    def _prompt_text(self, title: str, text: str, default: str = "") -> str:
        value = self._prompter.text(title, text, default)
        if value is None:
            raise ValueError(f"{title} cancelado")
        return value.strip()

    def _prompt_int(self, title: str, text: str, default: int = 0) -> int:
        raw = self._prompt_text(title, text, str(default))
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"{title}: numero invalido '{raw}'")

    def _start_event_listener(self, state: TuiState) -> None:
        self._stop_event_listener()
        stop_event = threading.Event()
        subscriber = self._subscriber_factory(state.redis_url, state.events_channel)

        self._event_stop_event = stop_event
        self._event_thread = threading.Thread(
            target=subscriber.listen,
            args=(stop_event, self._handle_event),
            daemon=True,
        )
        self._event_thread.start()

    def _stop_event_listener(self) -> None:
        if self._event_stop_event is not None:
            self._event_stop_event.set()
        if self._event_thread is not None and self._event_thread is not threading.current_thread():
            self._event_thread.join(timeout=1.0)
        self._event_stop_event = None
        self._event_thread = None

    def _handle_event(self, event: dict) -> None:
        line = self._formatter.format(event)
        self._event_lines.append(line)
        self._event_printer(line)


def _default_first(values: Sequence[Choice], default: str) -> Sequence[Choice]:
    selected = [item for item in values if item[0] == default]
    rest = [item for item in values if item[0] != default]
    return selected + rest
