"""

Owl/logging

This file contains routines for handling error messages.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.

"""

import sys


class Logger:
    def __init__(self, verbose=True, logstreams=None):
        self._verbose = verbose
        self._prevState = self._verbose
        if logstreams is None or logstreams == [] or len(logstreams) > 2:
            self._logstreams = [sys.stdout, sys.stderr]
            self.vprint('Using stdout and stderr as stream loggers.')
        elif len(logstreams) == 2:
            self._logstreams = logstreams
            self.vprint('Using logstreams as stream loggers.')
        elif len(logstreams) == 1:
            self._logstreams = 2*logstreams
            self.vprint('Using logstream as stream logger.')
        else:
            raise ValueError('Log streams %r must be a list.' % logstreams)

    def setVerbose(self, verbose=True):
        """
        Set verbose to True if you want the module to be chatty,
        or False to make it silent.
        """
        self._prevState = self._verbose
        self._verbose = verbose
        self.vprint('Setting verbose to', verbose)

        return self._prevState

    def resetVerbose(self):
        """
        Reset verbose to previous state.
        """
        self._verbose = self._prevState

    def print(self, *args, **kwargs):
        """
        Unconditional printing regardless of the value of the verbose variable
        previously set.
        """
        if 'file' not in kwargs:
            file = self._logstreams[0]
            kwargs['file'] = file

        print(*args, **kwargs)
        file.flush()

    def vprint(self, *args, **kwargs):
        """
        Conditional printing depending on the value of the verbose variable
        previously set.
        """
        if self._verbose:
            self.print(*args, **kwargs)

    def xprint(self, *args, **kwargs):
        """
        Print message and exit. Use to print error messages on stderr.
        The exit() used throws an exception in an interactive environment.
        """
        if 'file' not in kwargs:
            file = self._logstreams[1]
            kwargs['file'] = file

        if self._verbose:
            print('ERROR:', *args, **kwargs)
            print('Exiting...')
            file.flush()

        raise Exception('Fatal error.')
        # sys.exit(-1)
