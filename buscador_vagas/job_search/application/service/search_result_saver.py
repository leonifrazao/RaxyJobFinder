from __future__ import annotations

from job_search.application.dto.input.job_search_request import JobSearchRequest
from job_search.application.events.search_event import SearchEventName
from job_search.application.ports import JobRepository, JobSearchView, SearchEventReporter, SearchResultSaverPort
from job_search.domain.job_posting import JobPosting



class SearchResultSaver(SearchResultSaverPort):
    def __init__(self, repository: JobRepository, view: JobSearchView, event_reporter: SearchEventReporter) -> None:
        self.repository = repository
        self.view = view
        self.event_reporter = event_reporter

    def save_empty_outputs(self, request: JobSearchRequest) -> None:
        self.repository.save_jobs(request.jobs_output, [])
        self.repository.save_jobs(request.details_output, [])

    def save_results(self, request: JobSearchRequest, filtered_jobs: list[JobPosting]) -> None:
        self.event_reporter.publish(SearchEventName.SAVE_STARTED, "Salvando vagas...")
        self.repository.save_jobs(request.jobs_output, [job.summary for job in filtered_jobs])
        self.view.info(f"[bold green]Vagas salvas em:[/] {request.jobs_output}")
        self.event_reporter.publish(SearchEventName.SAVE_DETAILS_STARTED, "Salvando detalhes...")
        self.repository.save_jobs(request.details_output, filtered_jobs)
        self.view.info(f"[bold green]Vagas detalhadas salvas em:[/] {request.details_output}")
        self.event_reporter.publish(SearchEventName.SAVE_FINISHED, "Resultados salvos", jobs_output=request.jobs_output, details_output=request.details_output)
