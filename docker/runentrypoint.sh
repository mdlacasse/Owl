#!/bin/bash
#
# Docker entrypoint: launch the Owl Streamlit app.
#
# Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

if ! [[ -v OWL_DIR ]]; then
    OWL_DIR=/app/owl
fi

export PYTHONPATH=${OWL_DIR}/src:${PYTHONPATH}

echo ""
echo "Owl is now running locally: Point your browser to http://localhost:8501"
echo "Other network addresses are turned off for security reasons."

cd ${OWL_DIR}
${OWL_DIR}/.venv/bin/streamlit run ${OWL_DIR}/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.serverAddress=localhost --browser.gatherUsageStats=false

