::
:: A simple script to build Python package
::
cd ..
del /Q dist\*

for /f "usebackq delims=" %%t in (`python -c "import configparser,pathlib;c=configparser.ConfigParser();c.read(str(pathlib.Path.home()/'.pypirc'));print(c['pypi']['password'])"`) do set UV_PUBLISH_TOKEN=%%t

uv build
uv publish
