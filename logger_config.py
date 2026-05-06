"""
Shared logging configuration using Rich.

Usage:
    from logger_config import get_logger
    logger = get_logger(__name__)
"""

import logging
from rich.logging import RichHandler
from rich.console import Console

_CONSOLE = Console(stderr=True)

_FORMAT = "%(name)s | %(funcName)s:%(lineno)d | %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=_FORMAT,
    datefmt="[%Y-%m-%d %H:%M:%S]",
    handlers=[
        RichHandler(
            console=_CONSOLE,
            rich_tracebacks=True,
            show_time=True,
            show_level=True,
            show_path=True,
            markup=True,
            log_time_format="[%Y-%m-%d %H:%M:%S]",
        )
    ],
)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger configured with Rich handler."""
    return logging.getLogger(name)

