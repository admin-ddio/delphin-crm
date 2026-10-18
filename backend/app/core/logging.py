"""Structured logging: JSON in production, pretty console output in development."""

from __future__ import annotations

import logging
from typing import Any

import structlog

from app.core.config import Settings

_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
]


def configure_logging(settings: Settings) -> None:
    """Route stdlib and structlog output through one formatter on stderr."""
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.json_logs
        else structlog.dev.ConsoleRenderer()
    )
    processors: list[Any] = [*_SHARED_PROCESSORS]
    if settings.json_logs:
        processors.append(structlog.processors.format_exc_info)

    structlog.configure(
        processors=[*processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)

    # Server loggers propagate to root; RequestContextMiddleware writes the access lines.
    for name in ("uvicorn", "uvicorn.error", "gunicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger


def instrument(app: Any) -> None:
    """OpenTelemetry hook point.

    No exporter is configured in the scaffold. To enable tracing, install
    `opentelemetry-instrumentation-fastapi` and call
    `FastAPIInstrumentor.instrument_app(app)` here, driven by OTEL_* env vars.
    """
