#!/bin/bash
#
# Build both Owl Docker images.
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
##
## A simple script to build both Docker images
##
set -e
VERSION=$(python3 -c "exec(open('../src/owlplanner/version.py').read()); print(__version__)")

docker build --platform linux/amd64 --provenance=true --sbom=true --no-cache -f Dockerfile.edge -t owlplanner/owldocker:edge .
docker push owlplanner/owldocker:edge

docker build --platform linux/amd64 --provenance=true --sbom=true --no-cache -f Dockerfile.versioned -t owlplanner/owldocker:${VERSION} -t owlplanner/owldocker:latest .
docker push owlplanner/owldocker:${VERSION}
docker push owlplanner/owldocker:latest
