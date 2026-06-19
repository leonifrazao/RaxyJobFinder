from __future__ import annotations

from buscador_vagas.job_search.domain.job_posting import JobPosting
from buscador_vagas.job_search.domain.job_summary import JobSummary
from buscador_vagas.job_search.domain.location_option import LocationOption


class SilentView:
    def info(self, message: str) -> None:
        pass

    def warn(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass

    def choose_location(self, options: list[LocationOption], selected_index: int | None) -> LocationOption:
        if not options:
            raise RuntimeError("Nenhuma localizacao retornada pelo portal.")
        index = (selected_index or 1) - 1
        return options[max(0, min(index, len(options) - 1))]

    def show_jobs(self, jobs: list[JobSummary], limit: int) -> None:
        pass

    def show_job_details(self, jobs: list[JobPosting], limit: int) -> None:
        pass
