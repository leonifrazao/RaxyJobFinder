from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from job_search.domain.dtos import JobDetails, JobPosting, JobSummary, LocationOption
from job_search.view.rich_view import RichJobSearchView


@pytest.fixture
def view() -> RichJobSearchView:
    v = RichJobSearchView()
    v.console = MagicMock()
    return v


@pytest.fixture
def sample_job() -> JobSummary:
    return JobSummary(
        provider="linkedin", external_id="1", title="Engenheiro",
        company="ACME", location="SP", listed_at="2024-01-15", listed_text="1 semana atras",
        url="https://linkedin.com/jobs/1",
    )


@pytest.fixture
def sample_posting(sample_job: JobSummary) -> JobPosting:
    return JobPosting(
        summary=sample_job,
        details=JobDetails(
            title="Engenheiro Senior", company="ACME", location="SP",
            description="Vaga para engenheiro senior com 5+ anos de experiencia",
            criteria={"Nivel": "Senior", "Area": "Engenharia"},
        ),
        detail_status_code=200,
    )


@pytest.fixture
def locations() -> list[LocationOption]:
    return [
        LocationOption(id="1001", name="Sao Paulo", kind="city"),
        LocationOption(id="1002", name="Rio de Janeiro", kind="city"),
    ]


class TestInfo:
    def test_prints_message(self, view: RichJobSearchView):
        view.info("teste")
        view.console.print.assert_called_once_with("teste")


class TestWarn:
    def test_prints_yellow_message(self, view: RichJobSearchView):
        view.warn("cuidado")
        view.console.print.assert_called_once_with("[yellow]cuidado[/]")


class TestError:
    def test_prints_red_message(self, view: RichJobSearchView):
        view.error("erro")
        view.console.print.assert_called_once_with("[red]erro[/]")


class TestChooseLocation:
    def test_empty_options_raises(self, view: RichJobSearchView):
        with pytest.raises(RuntimeError, match="Nenhuma localizacao"):
            view.choose_location([], None)

    def test_with_selected_index_skips_prompt(self, view: RichJobSearchView, locations: list[LocationOption]):
        with patch("job_search.view.rich_view.IntPrompt") as mock_prompt:
            result = view.choose_location(locations, selected_index=2)

        assert result == locations[1]
        mock_prompt.ask.assert_not_called()
        view.console.print.assert_any_call(
            "[bold green]Localizacao selecionada:[/] Rio de Janeiro [dim](id=1002)[/]"
        )

    def test_without_selected_index_uses_prompt(self, view: RichJobSearchView, locations: list[LocationOption]):
        with patch("job_search.view.rich_view.IntPrompt") as mock_prompt:
            mock_prompt.ask.return_value = 1
            result = view.choose_location(locations, selected_index=None)

        assert result == locations[0]
        mock_prompt.ask.assert_called_once()

    def test_invalid_index_raises(self, view: RichJobSearchView, locations: list[LocationOption]):
        with pytest.raises(ValueError, match="entre 1 e 2"):
            view.choose_location(locations, selected_index=3)

    def test_index_zero_raises(self, view: RichJobSearchView, locations: list[LocationOption]):
        with pytest.raises(ValueError, match="entre 1 e 2"):
            view.choose_location(locations, selected_index=0)

    def test_shows_location_options_table(self, view: RichJobSearchView, locations: list[LocationOption]):
        with patch("job_search.view.rich_view.IntPrompt") as mock_prompt:
            mock_prompt.ask.return_value = 1
            view.choose_location(locations, None)

        assert view.console.print.call_count >= 2


class TestShowJobs:
    def test_empty_jobs_creates_table(self, view: RichJobSearchView):
        view.show_jobs([], 10)
        view.console.print.assert_called_once()
        table = view.console.print.call_args[0][0]
        assert "Vagas extraidas (0)" in table.title

    def test_limits_rows(self, view: RichJobSearchView, sample_job: JobSummary):
        jobs = [
            JobSummary(provider="linkedin", external_id=str(i), title=f"Job {i}", company="C")
            for i in range(20)
        ]
        view.show_jobs(jobs, limit=5)
        table = view.console.print.call_args[0][0]
        assert table.row_count == 5

    def test_shows_listed_text_preference(self, view: RichJobSearchView, sample_job: JobSummary):
        view.show_jobs([sample_job], 10)
        table = view.console.print.call_args[0][0]
        assert table.row_count == 1


class TestShowJobDetails:
    def test_filters_jobs_without_details(self, view: RichJobSearchView, sample_job: JobSummary):
        posting_no_details = JobPosting(summary=sample_job)
        view.show_job_details([posting_no_details], 10)
        table = view.console.print.call_args[0][0]
        assert "Detalhes extraidos (0)" in table.title

    def test_shows_detailed_jobs(self, view: RichJobSearchView, sample_posting: JobPosting):
        view.show_job_details([sample_posting], 10)
        table = view.console.print.call_args[0][0]
        assert table.row_count == 1

    def test_limits_rows(self, view: RichJobSearchView):
        postings = [
            JobPosting(
                summary=JobSummary(provider="gupy", external_id=str(i), title=f"Job {i}", company="C"),
                details=JobDetails(description="desc", criteria={"k": "v"}),
            )
            for i in range(20)
        ]
        view.show_job_details(postings, limit=3)
        table = view.console.print.call_args[0][0]
        assert table.row_count == 3

    def test_empty_list(self, view: RichJobSearchView):
        view.show_job_details([], 10)
        table = view.console.print.call_args[0][0]
        assert "Detalhes extraidos (0)" in table.title

    def test_shows_criteria_as_key_value(self, view: RichJobSearchView, sample_posting: JobPosting):
        view.show_job_details([sample_posting], 10)
        table = view.console.print.call_args[0][0]
        assert "Detalhes extraidos (1)" in table.title


class TestShowLocationOptions:
    def test_displays_options(self, view: RichJobSearchView, locations: list[LocationOption]):
        view._show_location_options(locations)
        table = view.console.print.call_args[0][0]
        assert "Localizacoes encontradas" in table.title
        assert table.row_count == 2

    def test_empty_options_shows_no_rows(self, view: RichJobSearchView):
        view._show_location_options([])
        table = view.console.print.call_args[0][0]
        assert table.row_count == 0
