@ECHO OFF
:: Change to suit your specific installation of Python
set root=C:\Users\%username%\Anaconda3
call %root%\Scripts\activate.bat

echo Hit Ctrl-C to terminate the server
cd ui
call streamlit run main.py --browser.gatherUsageStats=false
