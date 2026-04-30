@ECHO OFF
:: Change to suit your specific installation of Python
set root=C:\Users\%username%\Anaconda3
call %root%\Scripts\activate.bat

:: Script can pass arguments directly to streamlit.
:: For example: owlplanner.cmd --theme.base=light

echo Hit Ctrl-C to terminate the server.
:: set PYTHONPATH=.\src;%PYTHONPATH%
set options=--browser.gatherUsageStats=false --browser.serverAddress=localhost --server.fileWatcherType=auto %*

where /q streamlit
if ERRORLEVEL 1 (
    where /q python3
    if ERRORLEVEL 1 (
        echo Application cannot be started.
        exit /B
    )
    call python3 -m streamlit run .\ui\main.py %options%
) else (
    call streamlit run .\ui\main.py %options%
)
