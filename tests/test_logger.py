from io import StringIO

from owlplanner import mylogging as log


def test_logger1():
    strio = StringIO()
    mylog = log.Logger(True, [strio])
    msg1 = 'Hello'
    mylog.vprint(msg1)
    msg2 = strio.getvalue().splitlines()
    assert msg1 == msg2[-1]


def test_logger2():
    strio = StringIO()
    mylog = log.Logger(False, [strio])
    msg1 = 'Hello'
    mylog.vprint(msg1)
    msg2 = strio.getvalue()
    assert '' == msg2
