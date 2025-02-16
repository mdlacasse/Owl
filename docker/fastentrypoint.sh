#/bin/bash

echo "Owl is now running locally: Point your browser to http://localhost:8501"
if type -P streamlit >& /dev/null; then
    streamlit run /app/owl/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false
else
    python3 -m streamlit run /app/owl/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false
fi

