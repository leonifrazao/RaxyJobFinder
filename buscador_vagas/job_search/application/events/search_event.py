from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SearchEvent:
    name: str
    message: str
    level: str = "info"
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "message": self.message,
            "level": self.level,
            "payload": self.payload,
            "occurred_at": self.occurred_at,
        }
