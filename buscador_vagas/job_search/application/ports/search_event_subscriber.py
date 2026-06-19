from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Any, Protocol


class SearchEventSubscriber(Protocol):
    def listen(self, stop_event: Event, handler: Callable[[dict[str, Any]], None]) -> None:
        ...
