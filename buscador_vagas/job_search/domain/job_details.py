from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class JobDetails:
    title: str = ""
    company: str = ""
    company_url: str = ""
    location: str = ""
    posted_text: str = ""
    applicants_text: str = ""
    description: str = ""
    criteria: dict[str, str] = field(default_factory=dict)
    apply_text: str = ""
    url: str = ""
    logo_url: str = ""
    provider_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "detail_title": self.title,
            "detail_company": self.company,
            "detail_company_url": self.company_url,
            "detail_location": self.location,
            "detail_posted_text": self.posted_text,
            "detail_applicants_text": self.applicants_text,
            "description": self.description,
            "criteria": self.criteria,
            "apply_text": self.apply_text,
            "detail_url": self.url,
            "detail_logo_url": self.logo_url,
        }
        data.update(self.provider_data)
        return data
