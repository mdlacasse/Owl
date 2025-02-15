#!/bin/bash


echo Hit Ctrl-C to terminate the server
cd ui
if type -P streamlit; then
    streamlit run main.py
else
    python3 -m streamlit run main.py --browser.gatherUsageStats=false
fi
