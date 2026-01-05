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

    def show(self, x: float):
        """
        Display the current progress percentage.

        Args:
            x: Progress value between 0.0 and 1.0 (will be clamped to this range).
               Values outside this range will be clamped.
        """
        if self.mylog is None:
            return

        # Clamp x to [0, 1] range
        x = max(0.0, min(1.0, x))

        # Use single \r for carriage return (double \r\r is unnecessary)
        self.mylog.print(f"\r{u.pc(x, f=0)}", end="")

    def finish(self):
        """
        Finish the progress display by printing a newline.
        """
        if self.mylog is not None:
            self.mylog.print()
