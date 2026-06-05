@ECHO OFF

:: Script can pass arguments directly to streamlit.
:: For example: owlplanner.cmd --theme.base=light
::
:: Set OWL_SKIP_DISCLAIMER=1 to suppress the startup disclaimer dialog.
:: For example: set OWL_SKIP_DISCLAIMER=1 && owlplanner.cmd

echo Hit Ctrl-C to terminate the server.
set options=--browser.gatherUsageStats=false --browser.serverAddress=localhost --server.fileWatcherType=auto %*
uv run streamlit run .\ui\main.py %options%
