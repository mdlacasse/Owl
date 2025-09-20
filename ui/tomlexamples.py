import requests
import streamlit as st
from io import StringIO, BytesIO


cases = ["jack+jill", "joe", "john+sally", "jon+jane", "kim+sam-bequest",
         "kim+sam-spending", "drawdowncalc-comparison-1"]


wages = ["jack+jill", "joe", "john+sally", "jon+jane",
         "kim+sam", "charles"]


def loadCaseExample(case):
    url = f"https://github.com/mdlacasse/owl/blob/main/examples/case_{case}.toml?raw=true"
    response = requests.get(url)
    if response.ok:
        return StringIO(response.text)
    else:
        st.error(f"Failed to load case parameter file from GitHub: {response.status_code}.")
        return None


def loadWagesExample(case):
    url = f"https://github.com/mdlacasse/owl/blob/main/examples/{case}.xlsx?raw=true"
    response = requests.get(url)
    if response.ok:
        return BytesIO(response.content)
    else:
        st.error(f"Failed to load Wages and Contributions file from GitHub: {response.status_code}.")
        return None
