#/bin/bash

# Build at run time for smaller image but slower starts.
rm -rf /app/owl
cd /app && git clone --depth 1 https://github.com/mdlacasse/Owl.git owl

export OWLDIR=/app/owl

python -m pip install --no-cache-dir --upgrade pip
grep -v mosek requirements.txt > myrequirements.txt
cd ${OWLDIR} && python -m pip install -r myrequirements.txt


exec /usr/bin/runentrypoint.sh
