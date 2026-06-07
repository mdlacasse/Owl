#!/bin/bash

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
