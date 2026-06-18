#!/bin/bash
#
# Launch the Owl Streamlit app, passing arguments through to streamlit.
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

# Script can pass arguments directly to streamlit.
# For example: owlplanner.sh --theme.base=light
#
# Set OWL_SKIP_DISCLAIMER=1 to suppress the startup disclaimer dialog.
# For example: OWL_SKIP_DISCLAIMER=1 owlplanner.sh

echo Hit Ctrl-C to terminate the server.
options="--browser.gatherUsageStats=false --browser.serverAddress=localhost --server.fileWatcherType=auto $*"
uv run streamlit run ./ui/main.py $options
