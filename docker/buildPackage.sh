## !/bin/bash

cd ..
for file in dist/*.whl dist/*.tar.gz; do
    rm $file
done

touch uv.lock
python -m build .
rm uv.lock

twine upload --repository pypi dist/*
