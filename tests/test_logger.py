
from io import StringIO

from owlplanner import logging

def test_logger():
    strio = StringIO()
    mylog = logging.Logger(True, [strio])
    msg1 = 'Hello'
    mylog.vprint(msg1)
    msg2 = strio.getvalue()
    assert msg1 + '\n' == msg2
