#/bin/bash

# Build at run time for smaller image but slower starts.
rm -rf /app/owl
cd /app && git clone --depth 1 https://github.com/mdlacasse/Owl.git owl

export OWLDIR=/app/owl

python -m pip install --no-cache-dir --upgrade pip
cd $OWLDIR
grep -vi mosek requirements.txt | python -m pip install -r /dev/stdin


exec /usr/bin/runentrypoint.sh
