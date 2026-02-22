## !/bin/bash

set -e

cd ..
rm -f dist/*.whl dist/*.tar.gz

touch uv.lock
trap 'rm -f uv.lock' EXIT
python -m build .

twine upload --repository pypi dist/*
