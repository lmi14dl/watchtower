#!/usr/bin/env python3
"""
Shared logging utility for Watchtower.
All modules import from this to get consistent logging to both console and log files.

Usage in any module:
    from logutil import get_logger, log_info, log_error, log_success, log_warn

    logger = get_logger("watch_subfinder")
    log_info(logger, "Starting subdomain enumeration")
    log_error(logger, f"Failed: {e}")
    log_success(logger, "Found 150 subdomains")
    log_warn(logger, "Rate limited, waiting 5 seconds")
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# Base directory (parent of database/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

# Log levels with ANSI colors
class Colors:
    RESET = "\033[0m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

# Track which loggers have been created to avoid duplicate handlers
_initialized_loggers = set()


def get_log_file():
    """Return the log file path based on the current run date."""
    return os.path.join(LOG_DIR, f"watchtower_{datetime.now().strftime('%Y-%m-%d')}.log")


def get_logger(name="watchtower", level="INFO", file_level=None):
    """
    Create or retrieve a logger that writes to both console and log file.

    Args:
        name: Logger name (usually module name)
        level: Console log level
        file_level: File log level (defaults to same as level)
    """
    import logging

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture everything, filter at handler level

    if name not in _initialized_loggers:
        # File handler — always DEBUG to capture everything
        file_handler = logging.FileHandler(get_log_file())
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level.upper())

        class ColorFormatter(logging.Formatter):
            LEVEL_COLORS = {
                "DEBUG": Colors.GRAY,
                "INFO": Colors.CYAN,
                "WARNING": Colors.YELLOW,
                "ERROR": Colors.RED,
                "CRITICAL": Colors.MAGENTA,
            }

            def format(self, record):
                color = self.LEVEL_COLORS.get(record.levelname, "")
                reset = Colors.RESET if color else ""
                return f"{color}{super().format(record)}{reset}"

        console_formatter = ColorFormatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        logger.propagate = False
        _initialized_loggers.add(name)
    else:
        # Update console level if already initialized
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(level.upper())

    return logger


def log_info(logger, message):
    """Log an info message."""
    logger.info(message)


def log_error(logger, message, exc_info=False):
    """Log an error message."""
    logger.error(message, exc_info=exc_info)


def log_success(logger, message):
    """Log a success message (displayed as INFO but prefixed with checkmark)."""
    logger.info(f"[OK] {message}")


def log_warn(logger, message):
    """Log a warning message."""
    logger.warning(message)


def log_step(logger, message):
    """Log a major step / phase separator."""
    logger.info(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    logger.info(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    logger.info(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")


def log_phase(logger, message, color=None):
    """Log a phase marker (e.g. 'Phase 1: Sync programs')."""
    prefix = color or Colors.CYAN
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{timestamp}] {message}"
    logger.info(f"{prefix}{msg}{Colors.RESET}")
    # Also print to stdout directly for immediate visibility
    print(f"{prefix}{msg}{Colors.RESET}")
