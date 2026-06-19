from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger


_configured = False
DEFAULT_LOG_PATH = "logs/raxy.jsonl"
DEFAULT_ERROR_LOG_PATH = "logs/raxy-error.log"


def resolve_error_log_path() -> str:
    return os.getenv("RAXY_ERROR_LOG_PATH", DEFAULT_ERROR_LOG_PATH)


def configure_logging(
    *,
    level: str | None = None,
    log_path: str | None = None,
    error_log_path: str | None = None,
    force: bool = False,
    enqueue: bool = True,
) -> None:
    global _configured
    if _configured and not force:
        return

    selected_level = level or os.getenv("RAXY_LOG_LEVEL", "INFO")
    selected_path = Path(log_path or os.getenv("RAXY_LOG_PATH", DEFAULT_LOG_PATH))
    selected_error_path = Path(error_log_path or resolve_error_log_path())
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    selected_error_path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        selected_path,
        level=selected_level,
        serialize=True,
        enqueue=enqueue,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        selected_error_path,
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message} | {extra}",
        enqueue=enqueue,
        backtrace=False,
        diagnose=False,
    )

    if os.getenv("RAXY_LOG_STDERR") == "1":
        logger.add(
            sys.stderr,
            level=selected_level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}",
            backtrace=False,
            diagnose=False,
        )

    _configured = True
