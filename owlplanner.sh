#!/bin/bash

echo Hit Ctrl-C to terminate the server.
cd ui
export PYTHONPATH="../src:${PYTHONPATH}"
if type -P streamlit; then
    streamlit run main.py --browser.gatherUsageStats=false --browser.serverAddress=localhost
else
    python3 -m streamlit run main.py --browser.gatherUsageStats=false --browser.serverAddress=localhost
fi
