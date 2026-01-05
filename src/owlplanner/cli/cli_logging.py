"""
CLI logging configuration utilities.

This module provides logging configuration functions for the command-line
interface, including log level management and formatting.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
from loguru import logger

LOG_LEVELS = {
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


def configure_logging(log_level: str = "INFO"):
    log_level = log_level.upper()

    if log_level not in LOG_LEVELS:
        raise ValueError(f"Invalid log level: {log_level}")

    logger.remove()  # remove default handler

    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            #            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        backtrace=(log_level == "TRACE"),
        diagnose=(log_level == "TRACE"),
    )
