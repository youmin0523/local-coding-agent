"""Structured logging via structlog.

One configuration call (`configure_logging`) wires structlog to render either
human-friendly console output or line-delimited JSON. Throughout the codebase we
bind ``run_id`` / ``turn_id`` / ``tool_call_id`` to the context so every log line
mirrors the agent's event stream and can be traced end to end.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_configured = False


def configure_logging(fmt: str = "console", level: str = "INFO") -> None:
    """Configure structlog + stdlib logging. Idempotent."""
    global _configured
    if _configured:
        return

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None, **initial: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound logger, configuring logging with defaults on first use."""
    if not _configured:
        configure_logging()
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    if initial:
        logger = logger.bind(**initial)
    return logger
