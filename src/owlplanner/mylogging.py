"""
Logging utility module with support for multiple backends.

This module provides a flexible logging system that supports both standard
Python logging and loguru backends, with verbose mode control and stream management.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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
import threading
from contextlib import contextmanager

# Conditional import of loguru - only available if package is installed
try:
    from loguru import logger as loguru_logger

    HAS_LOGURU = True
except ImportError:
    loguru_logger = None  # type: ignore[assignment]
    HAS_LOGURU = False


# Tags name a severity, and the stream backend prints them verbatim. loguru has
# levels of its own, so a tag only survives that backend if it is mapped onto one:
# without this, a WARNING would arrive as DEBUG and be filtered out by any sink
# asking for warnings only.
_LOGURU_LEVELS = frozenset(["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"])


def _loguruLevel(tag, default):
    """Map a tag onto a loguru level name, falling back for one loguru does not know."""
    level = str(tag).strip().upper()
    return level if level in _LOGURU_LEVELS else default


# Stress tests fan out over a thread pool, and the worker clones log through the
# same destination as the parent (often the very same Logger object). Identity
# therefore cannot live on the Logger: it is kept per thread, and named by the
# scenario being solved when the caller knows it.
_threadCtx = threading.local()

# print() writes the message and its terminator separately, so two threads can
# tear a line in half. Lines are emitted under this lock.
_printLock = threading.Lock()


def setThreadLabel(label):
    """Name the current thread in the log, or clear its name with None."""
    _threadCtx.label = None if label is None else str(label)


@contextmanager
def threadLabel(label):
    """Name the current thread for the duration of the block, restoring any previous name."""
    previous = getattr(_threadCtx, "label", None)
    setThreadLabel(label)
    try:
        yield
    finally:
        setThreadLabel(previous)


def _threadTag():
    """Identify the emitting thread, or None when it is the unlabelled main thread."""
    label = getattr(_threadCtx, "label", None)
    if label:
        return label
    thread = threading.current_thread()
    return None if thread is threading.main_thread() else thread.name


def _threadMessage(args):
    """Join a message, prefixed with the emitting thread when it is not the main one.

    Owl configures no loguru sink of its own, so the default format is in force and
    bound extras would never be rendered: the prefix is what survives that backend.
    """
    message = " ".join(map(str, args))
    thread = _threadTag()
    return f"[{thread}] {message}" if thread else message


class Logger(object):
    def __init__(self, verbose=True, logstreams=None):
        self._verbose = verbose
        self._verboseStack = []  # Stack to track verbose states for proper restoration
        self._use_loguru = False

        # --- Detect loguru backend ---------------------------------
        if logstreams == "loguru" or logstreams == ["loguru"]:
            if not HAS_LOGURU:
                raise ImportError(
                    "loguru is required when using loguru logging backend. Install it with: pip install loguru"
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
        prev = self._verbose
        self._verboseStack.append(prev)
        self._verbose = verbose
        self.vprint("Setting verbose to", verbose)
        return prev

    def resetVerbose(self):
        if self._verboseStack:
            self._verbose = self._verboseStack.pop()

    def __deepcopy__(self, memo):
        """
        Custom deepcopy implementation to handle file descriptors properly.
        Creates a new Logger instance with the same settings instead of
        attempting to copy file descriptors (sys.stdout, sys.stderr, etc.).
        """
        # Determine logstreams parameter for new instance
        if self._use_loguru:
            logstreams = "loguru"
        elif self._logstreams == [sys.stdout, sys.stderr]:
            # Default case - will be recreated as [sys.stdout, sys.stderr]
            logstreams = None
        else:
            # Custom streams - preserve them (they might be StringIO or similar)
            logstreams = self._logstreams

        # Create a new Logger instance with the same settings
        new_logger = Logger(verbose=self._verbose, logstreams=logstreams)

        # Copy the verbose stack state
        new_logger._verboseStack = copy.deepcopy(self._verboseStack, memo)

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
        thread = _threadTag()
        if thread:
            formatted_message = f"{timestamp} | {tag} | {location} | {thread} | {message}"
        else:
            formatted_message = f"{timestamp} | {tag} | {location} | {message}"

        if "file" not in kwargs:
            kwargs["file"] = self._logstreams[stream_index]
        out = kwargs["file"]
        with _printLock:
            print(formatted_message, **kwargs)
            out.flush()

    def print(self, *args, tag="INFO", **kwargs):
        """
        Unconditional printing regardless of verbosity.
        """
        if self._use_loguru:
            loguru_logger.opt(depth=1).log(_loguruLevel(tag, "INFO"), _threadMessage(args))
            return
        self._stream_print(*args, tag=tag, stream_index=0, **kwargs)

    def vprint(self, *args, tag="DEBUG", **kwargs):
        """
        Conditional printing depending on verbose flag.
        """
        if not self._verbose:
            return
        if self._use_loguru:
            loguru_logger.opt(depth=1).log(_loguruLevel(tag, "DEBUG"), _threadMessage(args))
            return
        self._stream_print(*args, tag=tag, stream_index=0, **kwargs)
