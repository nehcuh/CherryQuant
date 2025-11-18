"""
Structured logging configuration for CherryQuant.

This module provides a standardized logging setup using structlog for
consistent, machine-readable logs across the application.
"""
import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log events."""
    event_dict["app"] = "cherryquant"
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    enable_colors: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON logs instead of human-readable format
        enable_colors: If True, enable colored output (only for non-JSON logs)
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Shared processors for all configurations
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_app_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable output for development
        processors = shared_processors + [
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(colors=enable_colors),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_login", user_id=123, ip_address="192.168.1.1")
        >>> logger.error("database_error", error=str(e), query="SELECT ...")
    """
    return structlog.get_logger(name)


# Configure logging on module import with sensible defaults
# This can be overridden by calling configure_logging() explicitly
configure_logging()
