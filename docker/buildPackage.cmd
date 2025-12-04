::
:: A simple script to build Python package
::
cd ..
del dist/*
python -m build .
twine upload --repository pypi dist/*
