from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


Choice = tuple[str, str]


class TuiPrompter(Protocol):
    def select(self, title: str, text: str, values: Sequence[Choice], default: str) -> str | None: ...
    def text(self, title: str, text: str, default: str = "") -> str | None: ...
    def confirm(self, title: str, text: str, default: bool = False) -> bool | None: ...
    def message(self, title: str, text: str) -> None: ...
