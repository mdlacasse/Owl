"""
Progress indicator for long-running operations.

This module provides a simple progress indicator class that displays
progress as a percentage on a single line that updates in place.

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

from typing import Optional
from owlplanner import utils as u


class Progress:
    """
    A simple progress indicator for long-running operations.

    Displays progress as a percentage (0-100%) on a single line that updates
    in place using carriage return.

    Example:
        prog = Progress(mylog)
        prog.start()
        for i in range(100):
            prog.show(i / 100)
        prog.finish()
    """

    def __init__(self, mylog: Optional[object] = None):
        """
        Initialize the progress indicator.

        Args:
            mylog: Logger object with a print() method. If None, progress
                   updates will be silently ignored (useful for Streamlit UI).
        """
        self.mylog = mylog

    def start(self):
        """
        Display the progress header.
        """
        if self.mylog is not None:
            self.mylog.print("|--- progress ---|")

    def show(self, n: int, N: int):
        """
        Display the current progress.

        Args:
            n: Current case number (1-based).
            N: Total number of cases.
        """
        if self.mylog is None:
            return

        x = max(0.0, min(1.0, n / N))
        self.mylog.print(f"\r{u.pc(x, f=0)} (case {n} of {N})", end="")

    def finish(self):
        """
        Finish the progress display by printing a newline.
        """
        if self.mylog is not None:
            self.mylog.print()
