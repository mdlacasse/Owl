import requests
import streamlit as st
from io import StringIO


cases = ["jack+jill", "joe", "john+sally", "jon+jane", "kim+sam-bequest", "kim+sam-spending"]


def loadExample(case):
    url = f"https://raw.github.com/mdlacasse/owl/main/examples/case_{case}.toml"
    response = requests.get(url)
    if response.status_code == 200:
        return StringIO(response.text)
    else:
        st.error(f"Failed to load case parameter file from GitHub: {response.status_code}.")
        return None
