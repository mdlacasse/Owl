#!/bin/bash
#
# Docker entrypoint: build Owl at container run time.
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

set -e

# Build at run time for smaller image but slower starts.
rm -rf /app/owl
cd /app && git clone --depth 1 https://github.com/mdlacasse/Owl.git owl

export OWL_DIR=/app/owl
cd $OWL_DIR

# Install from uv.lock, skipping the dev group and MOSEK (no license shipped in the image).
# --no-install-package overrides owlplanner's hard dependency on mosek; uv.lock is unchanged.
uv sync --frozen --no-dev --no-install-package mosek --no-cache

exec /usr/bin/runentrypoint.sh
