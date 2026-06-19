from __future__ import annotations

from typing import Any

from job_search.interfaces.tui.tui_state import TuiState


class TuiInputReader:
    def read(self, fields: dict[str, Any]) -> TuiState:
        return TuiState(
            portal=self._text(fields["portal"]),
            keywords=self._text(fields["keywords"]),
            location=self._text(fields["location"]),
            location_id=self._text(fields["location_id"]),
            location_choice=self._text(fields["location_choice"]),
            provider=self._text(fields["provider"]),
            valid_count=self._int(fields["valid_count"]),
            jobs_per_proxy=self._int(fields["jobs_per_proxy"]),
            max_count=self._int(fields["max_count"]),
            threads=self._int(fields["threads"]),
            timeout=self._float(fields["timeout"]),
            detail_timeout=self._float(fields["detail_timeout"]),
            max_jobs=self._int(fields["max_jobs"]),
            start=self._int(fields["start"]),
            details_limit=self._int(fields["details_limit"]),
            detail_threads=self._int(fields["detail_threads"]),
            show_jobs=self._int(fields["show_jobs"]),
            gd_cookie=self._text(fields["gd_cookie"]),
            filters_path=self._text(fields["filters_path"]),
            jobs_output=self._text(fields["jobs_output"]),
            details_output=self._text(fields["details_output"]),
            redis_url=self._text(fields["redis_url"]),
            events_channel=self._text(fields["events_channel"]),
        )

    @staticmethod
    def _text(field: Any) -> str:
        return str(field.value).strip()

    @classmethod
    def _int(cls, field: Any) -> int:
        raw = cls._text(field)
        return int(raw) if raw else 0

    @classmethod
    def _float(cls, field: Any) -> float:
        raw = cls._text(field)
        return float(raw) if raw else 0.0
