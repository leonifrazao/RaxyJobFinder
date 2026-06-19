from __future__ import annotations

from datetime import datetime
from typing import Any


class TuiEventFormatter:
    def format(self, event: dict[str, Any]) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        level = str(event.get("level") or "info").upper()
        message = str(event.get("message") or event.get("name") or "evento")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        portal = payload.get("portal")
        prefix = f"[{ts}] [{level}]"
        if portal:
            prefix = f"{prefix} {portal}"
        extras: list[str] = []
        bridges = payload.get("bridges_count")
        jobs = payload.get("jobs_count")
        status = payload.get("status_code")
        error = payload.get("error")
        working = payload.get("working")
        total = payload.get("total")
        idx = payload.get("index")
        total_bridges = payload.get("expected")
        if bridges is not None:
            extras.append(f"{bridges} bridges")
        if total_bridges is not None:
            extras.append(f"{total_bridges} bridges esperadas")
        if jobs is not None:
            extras.append(f"{jobs} vagas")
        if working is not None and total is not None:
            extras.append(f"{working}/{total} OK")
        elif total is not None:
            extras.append(f"{total} total")
        if idx is not None:
            extras.append(f"#{idx}")
        if status is not None:
            extras.append(f"HTTP {status}")
        if error is not None:
            extras.append(error)
        suffix = f" ({', '.join(extras)})" if extras else ""
        return f"{prefix} {message}{suffix}"
