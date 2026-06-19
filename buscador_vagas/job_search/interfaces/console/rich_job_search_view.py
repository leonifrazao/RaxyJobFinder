from __future__ import annotations

from rich.console import Console
from rich.prompt import IntPrompt
from rich.table import Table

from job_search.domain.job_posting import JobPosting
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption


class RichJobSearchView:
    def __init__(self) -> None:
        self.console = Console()

    def info(self, message: str) -> None:
        self.console.print(message)

    def warn(self, message: str) -> None:
        self.console.print(f"[yellow]{message}[/]")

    def error(self, message: str) -> None:
        self.console.print(f"[red]{message}[/]")

    def choose_location(self, options: list[LocationOption], selected_index: int | None) -> LocationOption:
        if not options:
            raise RuntimeError("Nenhuma localizacao retornada pelo portal.")
        self._show_location_options(options)
        if selected_index is None:
            selected_index = IntPrompt.ask("Escolha a localizacao", default=1)
        if selected_index < 1 or selected_index > len(options):
            raise ValueError(f"location-choice deve estar entre 1 e {len(options)}")
        selected = options[selected_index - 1]
        self.console.print(f"[bold green]Localizacao selecionada:[/] {selected.name} [dim](id={selected.id})[/]")
        return selected

    def show_jobs(self, jobs: list[JobSummary], limit: int) -> None:
        table = Table(title=f"Vagas extraidas ({len(jobs)})", show_lines=False)
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Titulo", overflow="fold")
        table.add_column("Empresa", overflow="fold")
        table.add_column("Local", overflow="fold")
        table.add_column("Data", no_wrap=True)
        for index, job in enumerate(jobs[:limit], start=1):
            table.add_row(str(index), job.title, job.company, job.location, job.listed_text or job.listed_at)
        self.console.print(table)

    def show_job_details(self, jobs: list[JobPosting], limit: int) -> None:
        detailed_jobs = [job for job in jobs if job.details and (job.details.description or job.details.criteria)]
        table = Table(title=f"Detalhes extraidos ({len(detailed_jobs)})", show_lines=False)
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Titulo", overflow="fold")
        table.add_column("Empresa", overflow="fold")
        table.add_column("Critérios", overflow="fold")
        table.add_column("Descrição", overflow="fold")
        for index, job in enumerate(detailed_jobs[:limit], start=1):
            details = job.details
            if details is None:
                continue
            criteria_text = "; ".join(f"{key}: {value}" for key, value in details.criteria.items())
            table.add_row(
                str(index),
                details.title or job.summary.title,
                details.company or job.summary.company,
                criteria_text,
                details.description[:180],
            )
        self.console.print(table)

    def _show_location_options(self, options: list[LocationOption]) -> None:
        table = Table(title="Localizacoes encontradas", show_lines=False)
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("id", style="green", no_wrap=True)
        table.add_column("Nome")
        table.add_column("Tipo", style="dim", no_wrap=True)
        for index, item in enumerate(options, start=1):
            table.add_row(str(index), item.id, item.name, item.kind or "-")
        self.console.print(table)
