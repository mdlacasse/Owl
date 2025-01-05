"""
A simple object to display progress in Streamlit.

"""

import streamlit as st


class Progress:
    def __init__(self, mylog):
        self.mylog = mylog
        self.counter = 0
        self.clocks = []
        for i in range(1, 13):
            self.clocks.extend([':clock%d:' % i, ':clock%d30:' % i])
        self.txt = 'Calculations in progress. Please wait. '

    def msg(self):
        self.counter += 1
        return self.txt + self.clocks[(self.counter - 1) % 24]

    def start(self):
        self.bar = st.progress(0, self.msg())

    def show(self, x):
        self.bar.progress(x, self.msg())

    def finish(self):
        self.bar.empty()
