"""
Progress indicator component for Streamlit UI.

This module provides a simple progress indicator class that displays
progress updates in the Streamlit interface during long-running operations.

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

import streamlit as st


class Progress:
    _HOURGLASSES = ["⏳", "⌛"]
    _TXT = "Calculations in progress. Please wait... &nbsp; &nbsp;"

    def __init__(self, mylog):
        self.mylog = mylog
        self.counter = 0

    def start(self):
        self.bar = st.progress(0, self._TXT + self._HOURGLASSES[0])

    def show(self, n, N):
        hourglass = self._HOURGLASSES[self.counter % 2]
        self.counter += 1
        self.bar.progress(n / N, f"{self._TXT}{hourglass} &nbsp; Case {n} of {N}")

    def finish(self):
        self.bar.empty()
