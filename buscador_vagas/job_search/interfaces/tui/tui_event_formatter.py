from __future__ import annotations

from typing import Any


class TuiEventFormatter:
    def format(self, event: dict[str, Any]) -> str:
        level = str(event.get("level") or "info").upper()
        message = str(event.get("message") or event.get("name") or "evento")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        portal = payload.get("portal")
        prefix = f"[{level}]"
        if portal:
            prefix = f"{prefix} {portal}"
        return f"{prefix} {message}"
