#
# Build the Owl Python distribution (wheel + sdist).
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
## !/bin/bash

set -e

cd ..
rm -f dist/*.whl dist/*.tar.gz

export UV_PUBLISH_TOKEN=$(python -c "import configparser,pathlib; c=configparser.ConfigParser(); c.read(pathlib.Path.home()/'.pypirc'); print(c['pypi']['password'])")

uv build
uv publish
