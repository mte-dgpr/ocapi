#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Utilities for centralised logging management.

This module provides an ``initialize_root_logger`` function that configures
the application root logger with:
- Detailed format with timestamp and module name
- Console and file handlers
- Log file rotation by size and by day
- Configurable logging levels
"""

import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Detailed log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def initialize_root_logger(
    level: LogLevel = "INFO",
    log_file: Path | None = None,
    max_bytes: int = 1024 * 1024,  # 1024 KB default
    backup_count: int = 5,
    use_timed_rotation: bool = True,
    console_output: bool = True,
) -> logging.Logger:
    """Initialise and configure the application root logger.

    This function should be called once at application startup
    (typically in main or the CLI).

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Log file path. If None, no file logging.
        max_bytes: Maximum log file size before rotation (in bytes).
        backup_count: Number of backup files to keep.
        use_timed_rotation: If True, daily rotation in addition to size rotation.
        console_output: If True, print logs to the console.

    Returns:
        The configured root logger.

    Example:
        >>> from ocapi.utils.logging_utils import initialize_root_logger
        >>> from pathlib import Path
        >>> logger = initialize_root_logger(
        ...     level="INFO",
        ...     log_file=Path("logs/ocapi.log"),
        ...     console_output=True
        ... )
        >>> logger.info("Application started")
    """
    root_logger = logging.getLogger()

    log_level = getattr(logging, level.upper())
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if use_timed_rotation:
            # Daily rotation only
            # Note: do not combine TimedRotatingFileHandler and RotatingFileHandler
            # on the same file to avoid conflicts
            file_handler: logging.Handler = TimedRotatingFileHandler(
                filename=str(log_file),
                when="midnight",
                interval=1,
                backupCount=backup_count,
                encoding="utf-8",
            )
        else:
            # Size-based rotation only
            file_handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )

        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Should be called in each module to obtain a named logger.

    Args:
        name: Module name (typically __name__).

    Returns:
        Logger configured for this module.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Log message")
    """
    return logging.getLogger(name)


def set_level(level: LogLevel) -> None:
    """Change the global logging level.

    Args:
        level: New logging level.

    Example:
        >>> set_level("DEBUG")
    """
    log_level = getattr(logging, level.upper())
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        handler.setLevel(log_level)


__all__ = [
    "initialize_root_logger",
    "get_logger",
    "set_level",
    "LogLevel",
]
