from __future__ import annotations

from job_search.domain.location_option import LocationOption
from job_search.interfaces.tui.tui_prompter import TuiPrompter


class TuiJobSearchView:
    def __init__(self, prompter: TuiPrompter) -> None:
        self._prompter = prompter
        self._location_result: LocationOption | None = None

    def info(self, message: str) -> None:
        pass

    def warn(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass

    def choose_location(self, options: list[LocationOption], selected_index: int | str | None) -> LocationOption:
        if not options:
            raise RuntimeError("Nenhuma localizacao retornada pelo portal.")
        index: int | None = None
        if selected_index is not None:
            try:
                index = int(selected_index)
            except (TypeError, ValueError):
                pass
        if index is not None and 1 <= index <= len(options):
            selected = options[index - 1]
            self._location_result = selected
            return selected
        entries = [(str(i + 1), f"{item.name} ({item.kind or '-'})") for i, item in enumerate(options)]
        result = self._prompter.select("Localizacao", "Escolha a localizacao:", entries, "1")
        if result is None:
            self._location_result = options[0]
            return options[0]
        selected = options[int(result) - 1]
        self._location_result = selected
        return selected

    def show_jobs(self, jobs, limit):
        pass

    def show_job_details(self, jobs, limit):
        pass
