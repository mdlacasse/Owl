import sys
import copy
import re
from loguru import logger as loguru_logger


class Logger(object):
    def __init__(self, verbose=True, logstreams=None, stream_id=None):
        self._verbose = verbose
        self._prevState = self._verbose
        self._verboseStack = []  # Stack to track verbose states for proper restoration
        self._use_loguru = False
        self._stream_id = stream_id

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

    def setStreamId(self, stream_id):
        """
        Update the stream_id used for tagging log messages.
        """
        self._stream_id = stream_id

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
            logstreams=logstreams,
            stream_id=self._stream_id
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

        tag = self._stream_id + " | " if self._stream_id else "Global |"
        loguru_logger.opt(depth=1).info(tag + (" ".join(map(str, args))))

        if "file" not in kwargs:
            file = self._logstreams[0]
            kwargs["file"] = file

        print(*args, **kwargs)
        file.flush()

    def vprint(self, *args, **kwargs):
        """
        Conditional printing depending on verbose flag.
        """
        if self._verbose:
            if self._use_loguru:
                loguru_logger.debug(" ".join(map(str, args)))
                return

            tag = self._stream_id + " | " if self._stream_id else "Global | "
            loguru_logger.opt(depth=1).debug(tag + (" ".join(map(str, args))))

            if "file" not in kwargs:
                file = self._logstreams[0]
                kwargs["file"] = file

            print(*args, **kwargs)
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


# -------------------------------
# Log filtering utility functions
# -------------------------------


def parse_log_groups(log_content):
    """
    Parse log content into message groups.

    Groups multi-line log messages together. A log entry starts with a timestamp
    pattern (YYYY-MM-DD HH:mm:ss), and continuation lines (without timestamps)
    are grouped with the preceding entry.

    Args:
        log_content (str): Raw log content from StringIO or similar

    Returns:
        list: List of message groups, where each group is a list of lines
    """
    lines = log_content.splitlines()
    # Pattern to detect log entry start: timestamp at beginning of line
    # Log format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{line} | {message}"
    timestamp_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

    message_groups = []
    current_group = []

    for line in lines:
        # Check if this line starts a new log entry
        if timestamp_pattern.match(line):
            # Save previous group if it exists
            if current_group:
                message_groups.append(current_group)
            # Start new group
            current_group = [line]
        else:
            # Continuation line - add to current group
            if current_group:
                current_group.append(line)
            else:
                # Orphaned continuation line (shouldn't happen, but handle gracefully)
                current_group = [line]

    # Don't forget the last group
    if current_group:
        message_groups.append(current_group)

    return message_groups


def filter_log_groups(message_groups, case_filter=None, text_filter=None):
    """
    Filter message groups by case name and/or text content.

    A message group is included if it matches the filters. The case filter
    is only checked in the first line (which contains the loguru format with
    the case tag), while the text filter is checked across all lines in the group.
    This ensures multi-line messages are preserved when filtering.

    Args:
        message_groups (list): List of message groups (from parse_log_groups)
        case_filter (str, optional): Case name to filter by (looks for "| {case} |")
        text_filter (str, optional): Text substring to search for

    Returns:
        list: Filtered list of message groups
    """
    filtered_groups = []

    for group in message_groups:
        # Check if the group matches the filters
        matches_case = True
        matches_text = True

        if case_filter:
            # Case tag only appears in the first line (the loguru-formatted line)
            casestr = "| " + case_filter + " |"
            matches_case = casestr in group[0]

        if text_filter:
            # Text filter can match any line in the group
            matches_text = any(text_filter in line for line in group)

        # Include group if it matches all active filters
        if matches_case and matches_text:
            filtered_groups.append(group)

    return filtered_groups


def format_filtered_logs(filtered_groups):
    """
    Format filtered message groups back into a single string.

    Args:
        filtered_groups (list): List of filtered message groups

    Returns:
        str: Formatted log content with newlines between lines
    """
    filtered_lines = []
    for group in filtered_groups:
        filtered_lines.extend(group)
    return "\n".join(filtered_lines)
