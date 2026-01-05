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
    def __init__(self, mylog):
        self.mylog = mylog
        self.counter = 0
        self.clocks = []
        for i in range(1, 13):
            self.clocks.extend([f":clock{i}:", f":clock{i}30:"])
        self.txt = "Calculations in progress. Please wait. "

    def msg(self):
        self.counter += 1
        return self.txt + self.clocks[(self.counter - 1) % 24]

    def start(self):
        self.bar = st.progress(0, self.msg())

    def show(self, x):
        self.bar.progress(x, self.msg())

    def finish(self):
        self.bar.empty()
