#!/bin/bash

if ! [[ -v OWL_DIR ]]; then
    OWL_DIR=/app/owl
fi

export PYTHONPATH=${OWL_DIR}/src:${PYTHONPATH}

echo ""
echo "Owl is now running locally: Point your browser to http://localhost:8501"
echo "Other network addresses are turned off for security reasons."

cd ${OWL_DIR}
${OWL_DIR}/.venv/bin/streamlit run ${OWL_DIR}/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.serverAddress=localhost --browser.gatherUsageStats=false

