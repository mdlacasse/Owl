#!/bin/bash

echo Hit Ctrl-C to terminate the server.
export PYTHONPATH="./src:${PYTHONPATH}"
if type -P streamlit >& /dev/null; then
    streamlit run ./ui/main.py --browser.gatherUsageStats=false --browser.serverAddress=localhost
else
    python3 -m streamlit run ./ui/main.py --browser.gatherUsageStats=false --browser.serverAddress=localhost
fi
