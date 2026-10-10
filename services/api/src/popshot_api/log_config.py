"""Structured JSON logging that Cloud Logging understands.

Every line is one JSON object on stdout with a `severity` field. The standard library
loggers (uvicorn, etc.) go through the same pipeline so nothing is logged as plain text.
"""

import logging
import sys
from typing import TextIO

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger


def _add_severity(_: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    level = event_dict.pop("level", method_name)
    event_dict["severity"] = "WARNING" if level == "warn" else str(level).upper()
    return event_dict


class _StdoutHandler(logging.StreamHandler[TextIO]):
    """Looks up sys.stdout on every write, so a replaced stdout (tests, reloaders) still works."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def configure_logging(level: str) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_severity,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="time"),
    ]

    structlog.configure(
        processors=[
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = _StdoutHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # We log requests ourselves (path only, never query strings or headers).
    logging.getLogger("uvicorn.access").disabled = True
    # HTTP client libraries log full URLs (query strings included) at INFO.
    for name in ("httpx", "httpx2", "httpcore", "httpcore2", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
