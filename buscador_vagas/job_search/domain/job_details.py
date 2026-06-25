from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


RequirementPattern = Mapping[str, str] | tuple[str, str]


def _requirement_pattern_pair(entry: RequirementPattern) -> tuple[str, str]:
    if isinstance(entry, Mapping):
        return entry.get("pattern", ""), entry.get("label", "")
    return entry


def extract_requisitos(
    description: str,
    patterns: Iterable[RequirementPattern] | None = None,
) -> list[str]:
    if not description or patterns is None:
        return []
    desc_lower = description.lower()
    found: set[str] = set()
    for entry in patterns:
        pattern, label = _requirement_pattern_pair(entry)
        if not pattern or not label:
            continue
        if re.search(pattern, desc_lower, re.IGNORECASE):
            found.add(label)
    return sorted(found)


@dataclass(frozen=True)
class JobDetails:
    title: str = ""
    company: str = ""
    company_url: str = ""
    location: str = ""
    posted_text: str = ""
    applicants_text: str = ""
    description: str = ""
    criteria: dict[str, Any] = field(default_factory=dict)
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
