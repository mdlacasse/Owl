"""
Logging utility module with support for multiple backends.

This module provides a flexible logging system that supports both standard
Python logging and loguru backends, with verbose mode control and stream management.

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
import copy
import inspect
import os

# Conditional import of loguru - only available if package is installed
try:
    from loguru import logger as loguru_logger
    HAS_LOGURU = True
except ImportError:
    loguru_logger = None
    HAS_LOGURU = False


class Logger(object):
    def __init__(self, verbose=True, logstreams=None):
        self._verbose = verbose
        self._prevState = self._verbose
        self._verboseStack = []  # Stack to track verbose states for proper restoration
        self._use_loguru = False

        # --- Detect loguru backend ---------------------------------
        if logstreams == "loguru" or logstreams == ["loguru"]:
            if not HAS_LOGURU:
                raise ImportError(
                    "loguru is required when using loguru logging backend. "
                    "Install it with: pip install loguru"
                )
            self._use_loguru = True
            self._logstreams = None

            loguru_logger.debug("Using loguru as logging backend.")
            return

        # --- Existing stream-based behavior ------------------------
        # First check if logstreams is a valid type (list or None)
        if logstreams is not None and not isinstance(logstreams, list):
            raise ValueError(f"Log streams {logstreams} must be a list.")

        if logstreams is None or logstreams == [] or len(logstreams) > 2:
            self._logstreams = [sys.stdout, sys.stderr]
            self.vprint("Using stdout and stderr as stream loggers.")
        elif len(logstreams) == 2:
            self._logstreams = logstreams
            self.vprint("Using logstreams as stream loggers.")
        elif len(logstreams) == 1:
            self._logstreams = 2 * logstreams
            self.vprint("Using logstream as stream logger.")

    def setVerbose(self, verbose=True):
        # Push current state onto stack before changing it
        self._verboseStack.append(self._verbose)
        self._prevState = self._verbose
        self._verbose = verbose
        self.vprint("Setting verbose to", verbose)
        return self._prevState

    def resetVerbose(self):
        # Pop the previous state from the stack if available
        if self._verboseStack:
            self._verbose = self._verboseStack.pop()
            self._prevState = self._verbose
        else:
            # Fallback to _prevState if stack is empty (shouldn't happen in normal usage)
            self._verbose = self._prevState

    def __deepcopy__(self, memo):
        """
        Custom deepcopy implementation to handle file descriptors properly.
        Creates a new Logger instance with the same settings instead of
        attempting to copy file descriptors (sys.stdout, sys.stderr, etc.).
        """
        # Determine logstreams parameter for new instance
        if self._use_loguru:
            logstreams = "loguru"
        elif self._logstreams is None:
            logstreams = None
        elif self._logstreams == [sys.stdout, sys.stderr]:
            # Default case - will be recreated as [sys.stdout, sys.stderr]
            logstreams = None
        else:
            # Custom streams - preserve them (they might be StringIO or similar)
            logstreams = self._logstreams

        # Create a new Logger instance with the same settings
        new_logger = Logger(
            verbose=self._verbose,
            logstreams=logstreams
        )

        # Copy the verbose stack state
        new_logger._verboseStack = copy.deepcopy(self._verboseStack, memo)
        new_logger._prevState = self._prevState

        return new_logger

    # ------------------------------------------------------------
    # Printing methods
    # ------------------------------------------------------------

    def _stream_print(self, *args, tag="INFO", stream_index=0, **kwargs):
        """
        Format message with caller location and timestamp, print to stream.
        Used by print() and vprint() for stream-based logging.
        """
        from datetime import datetime

        # Caller is one frame up from the method that called us (print/vprint)
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        if filename.endswith(".py"):
            filename = filename[:-3]
        location = f"{filename}:{frame.f_code.co_name}:{frame.f_lineno}"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = " ".join(map(str, args))
        formatted_message = f"{timestamp} | {tag} | {location} | {message}"

        if "file" not in kwargs:
            kwargs["file"] = self._logstreams[stream_index]
        out = kwargs["file"]
        print(formatted_message, **kwargs)
        out.flush()

    def print(self, *args, tag="INFO", **kwargs):
        """
        Unconditional printing regardless of verbosity.
        """
        if self._use_loguru:
            loguru_logger.opt(depth=1).debug(" ".join(map(str, args)))
            return
        self._stream_print(*args, tag=tag, stream_index=0, **kwargs)

    def vprint(self, *args, tag="DEBUG", **kwargs):
        """
        Conditional printing depending on verbose flag.
        """
        if not self._verbose:
            return
        if self._use_loguru:
            loguru_logger.opt(depth=1).debug(" ".join(map(str, args)))
            return
        self._stream_print(*args, tag=tag, stream_index=0, **kwargs)


# Log filtering utility functions removed - no longer needed since StringIO guarantees ordered messages
