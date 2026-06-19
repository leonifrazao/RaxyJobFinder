from __future__ import annotations

from typing import Any

from job_search.interfaces.tui.tui_state import TuiState


class TuiInputReader:
    def read(self, fields: dict[str, Any]) -> TuiState:
        return TuiState(
            portal=self._text(fields["portal"]),
            keywords=self._text(fields["keywords"]),
            location=self._text(fields["location"]),
            provider=self._text(fields["provider"]),
            valid_count=self._int(fields["valid_count"]),
            max_count=self._int(fields["max_count"]),
            threads=self._int(fields["threads"]),
            timeout=self._float(fields["timeout"]),
            detail_timeout=self._float(fields["detail_timeout"]),
            max_jobs=self._int(fields["max_jobs"]),
            details_limit=self._int(fields["details_limit"]),
            show_jobs=self._int(fields["show_jobs"]),
            jobs_output=self._text(fields["jobs_output"]),
            details_output=self._text(fields["details_output"]),
        )

    @staticmethod
    def _text(field: Any) -> str:
        return str(field.value).strip()

    @classmethod
    def _int(cls, field: Any) -> int:
        return int(cls._text(field))

    @classmethod
    def _float(cls, field: Any) -> float:
        return float(cls._text(field))
