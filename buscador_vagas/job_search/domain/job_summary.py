from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .text import clean_text


@dataclass(frozen=True)
class JobSummary:
    provider: str
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    listed_at: str = ""
    listed_text: str = ""
    url: str = ""
    company_url: str = ""
    logo_url: str = ""
    provider_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not clean_text(self.title) and not self.url:
            raise ValueError("job summary requires title or url")

    def to_dict(self) -> dict[str, Any]:
        data = {
            "provider": self.provider,
            "job_id": self.external_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "listed_at": _to_unix_timestamp(self.listed_at),
            "listed_text": self.listed_text,
            "url": self.url,
            "company_url": self.company_url,
            "logo_url": self.logo_url,
        }
        data.update(self.provider_data)
        return data


def _to_unix_timestamp(value: object) -> int | str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())
