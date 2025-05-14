#/bin/bash

# Build at run time for smaller image but slower starts.
rm -rf /app/owl
cd /app && git clone --depth 1 https://github.com/mdlacasse/Owl.git owl

export OWLDIR=/app/owl

python -m pip install --no-cache-dir --upgrade pip
cd ${OWLDIR} && python -m pip install -r requirements.txt

exec /usr/bin/runentrypoint.sh
