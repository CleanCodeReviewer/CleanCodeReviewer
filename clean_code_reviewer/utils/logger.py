"""Logging configuration for Clean Code Reviewer."""

from __future__ import annotations

import logging
import sys
from typing import TextIO


# Default log format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(levelname)s: %(message)s"


def setup_logging(
    level: int | str = logging.INFO,
    format_string: str | None = None,
    stream: TextIO | None = None,
    quiet: bool = False,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG, "INFO", "DEBUG")
        format_string: Custom format string (uses default if None)
        stream: Output stream (defaults to stderr)
        quiet: If True, suppress all output except errors
    """
    if quiet:
        level = logging.ERROR

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    if format_string is None:
        format_string = SIMPLE_FORMAT if level >= logging.INFO else DEFAULT_FORMAT

    if stream is None:
        stream = sys.stderr

    # Configure root logger for the package
    package_logger = logging.getLogger("clean_code_reviewer")
    package_logger.setLevel(level)

    # Remove existing handlers
    package_logger.handlers.clear()

    # Add new handler
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format_string))
    package_logger.addHandler(handler)

    # Prevent propagation to root logger
    package_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    # Ensure the name is under our package namespace
    if not name.startswith("clean_code_reviewer"):
        name = f"clean_code_reviewer.{name}"

    return logging.getLogger(name)


class LogLevel:
    """Convenience class for log level constants."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


def set_log_level(level: int | str) -> None:
    """
    Set the log level for the package.

    Args:
        level: New log level
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger("clean_code_reviewer")
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
