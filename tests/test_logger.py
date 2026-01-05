"""
Tests for mylogging module - logging functionality and backends.

Tests verify that the Logger class correctly handles logging operations
with different backends and verbosity settings.

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

from io import StringIO

from owlplanner import mylogging as log


def test_logger1():
    strio = StringIO()
    mylog = log.Logger(True, [strio])
    msg1 = 'Hello'
    mylog.vprint(msg1)
    msg2 = strio.getvalue().splitlines()
    # Logger now includes timestamp, location (file:function:line), and level
    # Check that the message is in the last line
    assert msg1 in msg2[-1]
    # Verify the format: timestamp | level | location | message
    assert '| DEBUG |' in msg2[-1]
    # Verify loguru-style location format (filename:function:line, without .py extension)
    assert 'test_logger:test_logger1:' in msg2[-1] or ':test_logger1:' in msg2[-1]


def test_logger2():
    strio = StringIO()
    mylog = log.Logger(False, [strio])
    msg1 = 'Hello'
    mylog.vprint(msg1)
    msg2 = strio.getvalue()
    assert '' == msg2
