# import requests
import streamlit as st
import os
from io import StringIO, BytesIO


cases = ["jack+jill", "joe", "john+sally", "jon+jane", "kim+sam-bequest",
         "kim+sam-spending", "drawdowncalc-comparison-1"]


wages = ["jack+jill", "joe", "john+sally", "jon+jane",
         "kim+sam", "charles"]


whereami = os.path.dirname(__file__)


def loadCaseExample(case):
    file = os.path.join(whereami, f"../examples/case_{case}.toml")
    with open(file, "r") as f:
        text = f.read()
        return StringIO(text)

    st.error(f"Failed to load case parameter file: {case}.")
    return None


def loadWagesExample(case):
    file = os.path.join(whereami, f"../examples/{case}.xlsx")
    with open(file, "rb") as f:
        data = f.read()
        return BytesIO(data)

    st.error(f"Failed to load Wages and Contributions file {case}.xlsx.")
    return None
