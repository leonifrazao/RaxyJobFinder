from __future__ import annotations

from dataclasses import dataclass
import os

from job_search.infrastructure.proxy.proxy_sources import DEFAULT_PROVIDER


@dataclass
class TuiState:
    portal: str = "linkedin"
    keywords: str = "Python"
    location: str = "Brasil"
    provider: str = DEFAULT_PROVIDER
    valid_count: int = 1
    max_count: int = 10
    threads: int = 3
    timeout: float = 15.0
    detail_timeout: float = 8.0
    max_jobs: int = 3
    details_limit: int = 1
    detail_threads: int = 5
    show_jobs: int = 3
    jobs_output: str = "output/linkedin/vagas.json"
    details_output: str = "output/linkedin/detalhadas.json"
    redis_url: str = os.getenv("RAXY_REDIS_URL", "redis://localhost:6379/0")
    events_channel: str = os.getenv("RAXY_REDIS_CHANNEL", "raxy:events")
