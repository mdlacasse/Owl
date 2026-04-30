#!/bin/bash

# Script can pass arguments directly to streamlit.
# For example: owlplanner.sh --theme.base=light

echo Hit Ctrl-C to terminate the server.
export PYTHONPATH="./src:${PYTHONPATH}"
options="--browser.gatherUsageStats=false --browser.serverAddress=localhost --server.fileWatcherType=auto $*"
if type -P streamlit >& /dev/null; then
    streamlit run ./ui/main.py $options
else
    python3 -m streamlit run ./ui/main.py $options
fi
