@ECHO OFF
:: Change to suit your specific installation of Python
set root=C:\Users\%username%\Anaconda3
call %root%\Scripts\activate.bat

cd ui
where /q streamlit
if ERRORLEVEL 1 (
    where /q python3
    if ERRORLEVEL 1 (
        echo Application cannot be started.
        exit /B
    ) else (
        echo Hit Ctrl-C to terminate the server.
        call python3 -m streamlit run main.py --browser.gatherUsageStats=false --browser.serverAddress=localhost
    )
) else (
    echo Hit Ctrl-C to terminate the Streamlit server.
    :: set PYTHONPATH=..\src;%PYTHONPATH%
    call streamlit run main.py --browser.gatherUsageStats=false --browser.serverAddress=localhost
)
