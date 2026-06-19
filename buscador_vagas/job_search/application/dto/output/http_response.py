from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HttpResponse:
    status_code: int | None
    url: str
    headers: dict[str, Any]
    text: str
    cookies: dict[str, str] = field(default_factory=dict)
