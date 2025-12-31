import sys
import copy
import inspect
import os
from loguru import logger as loguru_logger


class Logger(object):
    def __init__(self, verbose=True, logstreams=None):
        self._verbose = verbose
        self._prevState = self._verbose
        self._verboseStack = []  # Stack to track verbose states for proper restoration
        self._use_loguru = False

        # --- Detect loguru backend ---------------------------------
        if logstreams == "loguru" or logstreams == ["loguru"]:
            self._use_loguru = True
            self._logstreams = None

            loguru_logger.debug("Using loguru as logging backend.")
            return

        # --- Existing stream-based behavior ------------------------
        if logstreams is None or logstreams == [] or len(logstreams) > 2:
            self._logstreams = [sys.stdout, sys.stderr]
            self.vprint("Using stdout and stderr as stream loggers.")
        elif len(logstreams) == 2:
            self._logstreams = logstreams
            self.vprint("Using logstreams as stream loggers.")
        elif len(logstreams) == 1:
            self._logstreams = 2 * logstreams
            self.vprint("Using logstream as stream logger.")
        else:
            raise ValueError(f"Log streams {logstreams} must be a list.")

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

    def print(self, *args, **kwargs):
        """
        Unconditional printing regardless of verbosity.
        """

        if self._use_loguru:
            loguru_logger.debug(" ".join(map(str, args)))
            return

        # Get caller information (loguru style: name:function:line)
        frame = inspect.currentframe()
        caller_frame = frame.f_back
        filename = os.path.basename(caller_frame.f_code.co_filename)
        # Remove .py extension if present
        if filename.endswith('.py'):
            filename = filename[:-3]
        function_name = caller_frame.f_code.co_name
        line_number = caller_frame.f_lineno
        location = f"{filename}:{function_name}:{line_number}"

        # Format message with timestamp, location, and tag
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = " ".join(map(str, args))
        formatted_message = f"{timestamp} | INFO | {location} | {message}"

        if "file" not in kwargs:
            file = self._logstreams[0]
            kwargs["file"] = file

        print(formatted_message, **kwargs)
        file.flush()

    def vprint(self, *args, **kwargs):
        """
        Conditional printing depending on verbose flag.
        """
        if self._verbose:
            if self._use_loguru:
                loguru_logger.debug(" ".join(map(str, args)))
                return

            # Get caller information (loguru style: name:function:line)
            frame = inspect.currentframe()
            caller_frame = frame.f_back
            filename = os.path.basename(caller_frame.f_code.co_filename)
            # Remove .py extension if present
            if filename.endswith('.py'):
                filename = filename[:-3]
            function_name = caller_frame.f_code.co_name
            line_number = caller_frame.f_lineno
            location = f"{filename}:{function_name}:{line_number}"

            # Format message with timestamp, location, and tag
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = " ".join(map(str, args))
            formatted_message = f"{timestamp} | DEBUG | {location} | {message}"

            if "file" not in kwargs:
                file = self._logstreams[0]
                kwargs["file"] = file

            print(formatted_message, **kwargs)
            file.flush()

    def xprint(self, *args, **kwargs):
        """
        Print message and exit. Used for fatal errors.
        """
        if self._use_loguru:
            loguru_logger.debug("ERROR: " + " ".join(map(str, args)))
            loguru_logger.debug("Exiting...")
            raise Exception("Fatal error.")

        if "file" not in kwargs:
            file = self._logstreams[1]
            kwargs["file"] = file

        if self._verbose:
            print("ERROR:", *args, **kwargs)
            print("Exiting...")
            file.flush()

        raise Exception("Fatal error.")


# Log filtering utility functions removed - no longer needed since StringIO guarantees ordered messages
