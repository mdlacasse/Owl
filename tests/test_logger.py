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
