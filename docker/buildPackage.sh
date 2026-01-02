## !/bin/bash or similar

cd ..
rm dist/*.whl dist/*.tar.gz

touch uv.lock
python -m build .
rm uv.lock

twine upload --repository pypi dist/*
