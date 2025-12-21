::
:: A simple script to build Python package
::
cd ..
del /Q dist\*
type nul > uv.lock
python -m build .
del uv.lock

twine upload --repository pypi dist\*
