from __future__ import annotations


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split())
