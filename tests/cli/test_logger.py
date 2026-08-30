"""
Tests for mylogging module - logging functionality and backends.

Tests verify that the Logger class correctly handles logging operations
with different backends and verbosity settings.

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

import threading
from io import StringIO

from owlplanner import mylogging as log


def test_logger1():
    strio = StringIO()
    mylog = log.Logger(True, [strio])
    msg1 = "Hello"
    mylog.vprint(msg1)
    msg2 = strio.getvalue().splitlines()
    # Logger now includes timestamp, location (file:function:line), and level
    # Check that the message is in the last line
    assert msg1 in msg2[-1]
    # Verify the format: timestamp | level | location | message
    assert "| DEBUG |" in msg2[-1]
    # Verify loguru-style location format (filename:function:line, without .py extension)
    assert "test_logger:test_logger1:" in msg2[-1] or ":test_logger1:" in msg2[-1]


def test_logger2():
    strio = StringIO()
    mylog = log.Logger(False, [strio])
    msg1 = "Hello"
    mylog.vprint(msg1)
    msg2 = strio.getvalue()
    assert "" == msg2


def _logFromThread(mylog, name, label=None):
    """Emit one message from a worker thread and return the line it produced."""
    strio = mylog._logstreams[0]
    before = len(strio.getvalue().splitlines())

    def _emit():
        if label is None:
            mylog.print("Hello")
        else:
            with log.threadLabel(label):
                mylog.print("Hello")

    worker = threading.Thread(target=_emit, name=name)
    worker.start()
    worker.join()
    return strio.getvalue().splitlines()[before]


def test_main_thread_line_carries_no_thread_field():
    # The marker's presence is itself the signal that a line came from a worker,
    # so ordinary single-threaded output must keep its existing shape.
    strio = StringIO()
    mylog = log.Logger(True, [strio])
    mylog.print("Hello")
    line = strio.getvalue().splitlines()[-1]
    assert line.count("|") == 3
    assert "MainThread" not in line


def test_worker_line_carries_thread_name():
    strio = StringIO()
    mylog = log.Logger(True, [strio])
    line = _logFromThread(mylog, "scenario_3")
    assert "| scenario_3 |" in line
    assert "Hello" in line


def test_explicit_label_replaces_thread_name():
    # Pool threads are reused across scenarios, so a label naming the scenario is
    # more useful than the name of the slot that happened to run it.
    strio = StringIO()
    mylog = log.Logger(True, [strio])
    line = _logFromThread(mylog, "scenario_3", label=1965)
    assert "| 1965 |" in line
    assert "scenario_3" not in line


def test_thread_label_nests_and_restores():
    assert log._threadTag() is None
    with log.threadLabel("outer"):
        assert log._threadTag() == "outer"
        with log.threadLabel("inner"):
            assert log._threadTag() == "inner"
        assert log._threadTag() == "outer"
    # Back on the main thread with no label, nothing is reported.
    assert log._threadTag() is None


def test_loguru_message_is_prefixed_off_the_main_thread(monkeypatch):
    # Owl configures no loguru sink, so the marker has to ride in the message
    # itself: a bound extra would never be rendered by the default format.
    captured = []

    class _FakeLoguru:
        def opt(self, depth=0):
            _ = depth
            return self

        def log(self, level, message):
            captured.append((level, message))

        def debug(self, message):
            captured.append(("DEBUG", message))

    monkeypatch.setattr(log, "loguru_logger", _FakeLoguru())
    monkeypatch.setattr(log, "HAS_LOGURU", True)
    mylog = log.Logger(True, "loguru")

    mylog.print("Hello")
    assert captured[-1] == ("INFO", "Hello")

    worker = threading.Thread(target=lambda: mylog.print("Hello"), name="scenario_1")
    worker.start()
    worker.join()
    assert captured[-1] == ("INFO", "[scenario_1] Hello")
