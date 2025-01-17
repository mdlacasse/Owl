"""
A simple object to display progress.

"""

from owlplanner import utils as u


class Progress(object):
    def __init__(self, mylog):
        self.mylog = mylog

    def start(self):
        self.mylog.print('|--- progress ---|')

    def show(self, x):
        self.mylog.print('\r\r%s' % u.pc(x, f=0), end='')

    def finish(self):
        self.mylog.print()
