## !/bin/bash

set -e

cd ..
rm -f dist/*.whl dist/*.tar.gz

export UV_PUBLISH_TOKEN=$(python -c "import configparser,pathlib; c=configparser.ConfigParser(); c.read(pathlib.Path.home()/'.pypirc'); print(c['pypi']['password'])")

uv build
uv publish
