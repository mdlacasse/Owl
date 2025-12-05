::
:: A simple script to build Python package
::
cd ..
del /Q dist\*
python -m build .
twine upload --repository pypi dist\*
