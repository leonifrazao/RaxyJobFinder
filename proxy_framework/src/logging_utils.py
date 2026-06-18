from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def get_logger(name: str = "proxy_framework") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


log = get_logger()


def debug_log(
    enabled: bool = True,
    log_args: bool = True,
    log_result: bool = True,
    log_duration: bool = True,
    max_arg_length: int = 100,
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        if not enabled:
            return func

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger()
            func_name = getattr(func, "__qualname__", func.__name__)
            args_str = ""
            if log_args:
                args_str = _format_arguments(args, kwargs, max_arg_length)
            logger.debug("-> %s(%s)", func_name, args_str)
            started_at = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception:
                if log_duration:
                    logger.debug("x %s() failed [%.3fs]", func_name, time.time() - started_at)
                raise
            duration = time.time() - started_at
            result_str = f" -> {_format_value(result, max_arg_length)}" if log_result else ""
            duration_str = f" [{duration:.3f}s]" if log_duration else ""
            logger.debug("<- %s()%s%s", func_name, result_str, duration_str)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def _format_arguments(args: tuple[Any, ...], kwargs: dict[str, Any], max_length: int) -> str:
    start_idx = 1 if args and hasattr(args[0], "__class__") else 0
    parts = [_format_value(arg, max_length) for arg in args[start_idx:]]
    parts.extend(f"{key}={_format_value(value, max_length)}" for key, value in kwargs.items())
    return ", ".join(parts)


def _format_value(value: Any, max_length: int) -> str:
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, str):
        return repr(value[:max_length] + "..." if len(value) > max_length else value)
    if isinstance(value, (list, tuple, set)):
        return f"{type(value).__name__}({len(value)} items)"
    if isinstance(value, dict):
        return f"dict({len(value)} keys)"
    return repr(value)[:max_length]
