#!/bin/bash

# Script can pass arguments directly to streamlit.
# For example: owlplanner.sh --theme.base=light
#
# Set OWL_SKIP_DISCLAIMER=1 to suppress the startup disclaimer dialog.
# For example: OWL_SKIP_DISCLAIMER=1 owlplanner.sh

echo Hit Ctrl-C to terminate the server.
options="--browser.gatherUsageStats=false --browser.serverAddress=localhost --server.fileWatcherType=auto $*"
uv run streamlit run ./ui/main.py $options
