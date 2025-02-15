## Installation steps

### To install and run a Docker image, please see these [instructions](docker/README.md).

### Requirements
These instructions are for installing the Python source code for Owl and run it on your computer.
You will need Python and `pip` installed on your computer for that purpose.

### Installation steps for end-users
You can install the Owl package directly from the [Python Package Index](http://pypi.org).
The following command will install the current version of owlplanner and all its dependencies:
```shell
pip install -r ui/requirements.txt
```

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
The -e instructs Python to load the live version in the current directory tree. 
### Running the streamlit frontend 
Running the Owl user interface locally from Windows:
```shell
./owlplanner.cmd
```
From Linux or MacOS:
```shell
./owlplanner.sh
```

### Publishing a version (for reference only)
Run checks before commit:
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
