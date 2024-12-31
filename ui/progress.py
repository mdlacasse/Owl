"""
A simple object to display progress in Streamlit.

"""

import streamlit as st


class Progress:
    def __init__(self, mylog):
        self.mylog = mylog
        self.msg = 'Calculations in progress. Please wait.'

    def start(self):
        self.bar = st.progress(0, self.msg)

    def show(self, x):
        self.bar.progress(x, self.msg)

    def finish(self):
        self.bar.empty()
