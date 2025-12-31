from io import StringIO

from owlplanner import mylogging as log


def test_logger1():
    strio = StringIO()
    mylog = log.Logger(True, [strio])
    msg1 = 'Hello'
    mylog.vprint(msg1)
    msg2 = strio.getvalue().splitlines()
    # Logger now includes timestamp and level, so check that the message is in the last line
    assert msg1 in msg2[-1]
    # Verify the format: timestamp | level | tag | message
    assert '| DEBUG |' in msg2[-1]
    assert 'Global |' in msg2[-1]


def test_logger2():
    strio = StringIO()
    mylog = log.Logger(False, [strio])
    msg1 = 'Hello'
    mylog.vprint(msg1)
    msg2 = strio.getvalue()
    assert '' == msg2
