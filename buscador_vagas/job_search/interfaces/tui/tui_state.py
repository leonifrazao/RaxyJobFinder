from __future__ import annotations

from dataclasses import dataclass, field
import os

from job_search.infrastructure.config import load_settings


@dataclass
class TuiState:
    portal: str = "linkedin"
    keywords: str = "Vagas"
    location: str = "Brasil"
    location_id: str = ""
    location_choice: str = "1"
    work_type: str = "normal"
    applicant_filter: str = "normal"
    provider: str = ""
    valid_count: int = 25
    jobs_per_proxy: int = 5
    max_count: int = 177
    threads: int = 8
    timeout: float = 15.0
    detail_timeout: float = 15.0
    max_jobs: int = 0
    start: int = 0
    details_limit: int = 0
    detail_threads: int = 5
    show_jobs: int = 10
    gd_cookie: str = ""
    filters_path: str = ""
    jobs_output: str = "output/linkedin/vagas.json"
    details_output: str = "output/linkedin/detalhadas.json"
    redis_url: str = "redis://localhost:6379/0"
    events_channel: str = "raxy:events"
    provider_data: dict = field(default_factory=dict)

    @classmethod
    def from_config(cls) -> TuiState:
        cfg = load_settings().defaults
        redis_cfg = load_settings().redis
        output_cfg = load_settings().output
        portal = cfg.portal
        return cls(
            portal=portal,
            keywords=cfg.keywords,
            location=cfg.location,
            location_id=cfg.location_id,
            location_choice=cfg.location_choice,
            work_type=cfg.work_type,
            applicant_filter=cfg.applicant_filter,
            provider=cfg.provider if hasattr(cfg, "provider") and cfg.provider else load_settings().proxy.default_provider,
            valid_count=cfg.valid_count,
            jobs_per_proxy=cfg.jobs_per_proxy,
            max_count=cfg.max_count,
            threads=cfg.threads,
            timeout=cfg.timeout if hasattr(cfg, "timeout") else 15.0,
            detail_timeout=cfg.detail_timeout,
            max_jobs=cfg.max_jobs,
            start=cfg.start,
            details_limit=cfg.details_limit,
            detail_threads=cfg.detail_threads,
            show_jobs=cfg.show_jobs,
            gd_cookie=cfg.gd_cookie,
            filters_path=cfg.filters_path,
            jobs_output=output_cfg.jobs_path.format(portal=portal),
            details_output=output_cfg.details_path.format(portal=portal),
            redis_url=redis_cfg.url,
            events_channel=redis_cfg.channel,
        )
