from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeEndpoint:
    index: int
    url: str

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("bridge index must be non-negative")
        if not self.url:
            raise ValueError("bridge url is required")
