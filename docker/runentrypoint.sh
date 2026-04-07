#!/bin/bash

if ! [[ -v OWLDIR ]]; then
    OWLDIR=/app/owl
fi

if [[ -f /app/venv/bin/activate ]]; then
    source /app/venv/bin/activate
fi

export PYTHONPATH=${OWLDIR}/src:${PYTHONPATH}

echo ""
echo "Owl is now running locally: Point your browser to http://localhost:8501"
echo "Other network addresses are turned off for security reasons."

if type -P streamlit >& /dev/null; then
    streamlit run ${OWLDIR}/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false
else
    python3 -m streamlit run ${OWLDIR}/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false
fi

