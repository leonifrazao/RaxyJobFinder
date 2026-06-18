from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Outbound, ProxyItem, ProxyTestResult

DEFAULT_CACHE_FILENAME = "proxy_cache.json"
CACHE_VERSION = 1


def safe_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def format_timestamp(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_base_entry(index: int, raw_uri: str, outbound: Outbound) -> ProxyItem:
    return ProxyItem(
        index=index,
        uri=raw_uri,
        tag=outbound.tag,
        outbound=outbound,
        protocol=str(outbound.config.get("protocol") or ""),
    )


def _parse_cached_result(data: Dict[str, Any]) -> ProxyTestResult:
    res = ProxyTestResult(
        status=data.get("status", "AGUARDANDO"),
        ip=data.get("ip"),
        country=data.get("country"),
        country_code=data.get("country_code"),
        country_name=data.get("country_name"),
        proxy_ip=data.get("proxy_ip"),
        proxy_country=data.get("proxy_country"),
        proxy_country_code=data.get("proxy_country_code"),
        error=data.get("error"),
        tested_at=data.get("tested_at", ""),
        cached=True,
    )
    ping_val = data.get("ping", data.get("ping_ms"))
    if ping_val is not None:
        res.ping_ms = safe_float(ping_val)
    ts_val = data.get("tested_at_ts")
    if ts_val is not None:
        res.tested_at_ts = safe_float(ts_val) or 0.0
    return res


def apply_cached_entry(entry: ProxyItem, cached_result: ProxyTestResult) -> ProxyItem:
    if not cached_result:
        return entry
    return replace(entry, result=cached_result)


def load_cache(cache_path: Path) -> Dict[str, ProxyTestResult]:
    try:
        raw_cache = cache_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}

    try:
        data = json.loads(raw_cache)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}

    cache_map: Dict[str, ProxyTestResult] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        uri = item.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            continue
        cache_map[uri] = _parse_cached_result(item)
    return cache_map


def save_cache(cache_path: Path, entries: List[ProxyItem]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    payload_entries = []
    for entry in entries:
        if not isinstance(entry, ProxyItem):
            continue
        data = entry.to_persistence_dict()
        if data.get("uri"):
            payload_entries.append(data)

    payload = {
        "version": CACHE_VERSION,
        "generated_at": format_timestamp(time.time()),
        "entries": payload_entries,
    }

    try:
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
