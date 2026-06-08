"""
CLI logging configuration utilities.

This module provides logging configuration functions for the command-line
interface, including log level management and formatting.

Copyright (C) 2025-2026 The Owl Authors

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
import logging

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def configure_logging(log_level: str = "INFO"):
    log_level = log_level.upper()

    level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="%(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        force=True,
    )
