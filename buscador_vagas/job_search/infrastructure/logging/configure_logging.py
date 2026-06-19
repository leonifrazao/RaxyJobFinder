from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

from loguru import logger

from job_search.infrastructure.config import load_settings


_configured = False


def resolve_error_log_path() -> str:
    return os.getenv("RAXY_ERROR_LOG_PATH", load_settings().logging.error_path)


def _redirect_warning(message, category, filename, lineno, file=None, line=None):
    logger.opt(depth=1).warning("{}: {} ({}:{})", category.__name__, str(message), filename, lineno)


def _global_excepthook(exc_type, exc_value, exc_traceback):
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("unhandled_exception: {exc_type.__name__}: {exc_value}", exc_type=exc_type, exc_value=exc_value)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def configure_logging(
    *,
    level: str | None = None,
    log_path: str | None = None,
    error_log_path: str | None = None,
    force: bool = False,
    enqueue: bool = False,
) -> None:
    global _configured
    if _configured and not force:
        return

    logging_cfg = load_settings().logging

    selected_level = level or os.getenv("RAXY_LOG_LEVEL", logging_cfg.level)
    selected_path = Path(log_path or os.getenv("RAXY_LOG_PATH", logging_cfg.path))
    selected_error_path = Path(error_log_path or resolve_error_log_path())
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    selected_error_path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        selected_path,
        level=selected_level,
        serialize=True,
        enqueue=enqueue,
        buffering=1,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        selected_error_path,
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message} | {extra}",
        enqueue=enqueue,
        buffering=1,
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

    warnings.showwarning = _redirect_warning

    warnings.filterwarnings("always", category=ResourceWarning)
    try:
        import urllib3.exceptions
        warnings.filterwarnings("always", category=urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

    sys.excepthook = _global_excepthook

    _configured = True
