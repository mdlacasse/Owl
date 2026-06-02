#!/bin/bash

set -e

# Build at run time for smaller image but slower starts.
rm -rf /app/owl
cd /app && git clone --depth 1 https://github.com/mdlacasse/Owl.git owl

export OWL_DIR=/app/owl
cd $OWL_DIR

uv venv 
grep -vi mosek requirements.txt | uv pip install --no-cache-dir -r /dev/stdin

exec /usr/bin/runentrypoint.sh
