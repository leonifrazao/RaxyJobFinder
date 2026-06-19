from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LocationOption:
    id: str
    name: str
    kind: str = ""
    provider: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("location id is required")
        if not self.name:
            raise ValueError("location name is required")
