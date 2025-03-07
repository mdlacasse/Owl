# Owl

## A retirement exploration tool based on linear programming

<img align=right src="https://raw.github.com/mdlacasse/Owl/main/docs/images/owl.png" width="250">

------------------------------------------------------------------------------------
### About
This document is aimed at software developers desiring to install the Owl source code
and run it locally on their computer.

For end-users, we suggest accessing Owl from the [Streamlit Community Server](http://owlplanner.streamlit.app)
or, if one prefers to have everything on their own computer,
to install and run a Docker image as described in these [instructions](docker/README.md).

### Requirements
You will need Python and `pip` installed on your computer for completing the installation.

### Installation steps for developers
These instructions are command-line instructions.
You will need the latest version of Owl from GitHub.
```shell
git clone https://github.com/mdlacasse/Owl.git

```
Go (`cd`) to the directory where you installed Owl.
From the top directory of the source code run:
```shell
python -m build 
pip install -e .
```
The -e instructs `pip` to install in *editable* mode and use the live version
in the current directory tree.

### Running the streamlit frontend 
Running the Owl user interface locally from Windows:
```shell
./owlplanner.cmd
```
Running the Owl user interface locally from Linux or MacOS:
```shell
./owlplanner.sh
```

### Publishing a version (for reference only)
Run checks before all commits:
```
flake8 ui src tests
pytest
```
Edit version number in `src/owlplanner/version.py`, `ui/requirements.txt`, and in `pyproject.toml`. Then,
```shell
rm dist/*
python -m build
twine upload --repository [repo] dist/*
```
where [repo] is *testpypi* or *pypi* depending on the type of release.

### Installation steps for Python package only
You can install the Owl package directly from the [Python Package Index](http://pypi.org).
The following command will install the current version of owlplanner and all its dependencies:
```shell
pip install -r ui/requirements.txt
```

