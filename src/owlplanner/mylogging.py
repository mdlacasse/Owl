import sys
from loguru import logger as loguru_logger


class Logger(object):
    def __init__(self, verbose=True, logstreams=None, stream_id=None):
        self._verbose = verbose
        self._prevState = self._verbose
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
        self._prevState = self._verbose
        self._verbose = verbose
        self.vprint("Setting verbose to", verbose)
        return self._prevState

    def resetVerbose(self):
        self._verbose = self._prevState

    def setStreamId(self, stream_id):
        """
        Update the stream_id used for tagging log messages.
        """
        self._stream_id = stream_id

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
        # loguru_logger.info(tag+(" ".join(map(str, args))))
        loguru_logger.opt(depth=1).info(
            tag + (" ".join(map(str, args)))
        )
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
            # loguru_logger.debug(tag+(" ".join(map(str, args))))
            loguru_logger.opt(depth=1).debug(
                tag + (" ".join(map(str, args)))
            )

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
