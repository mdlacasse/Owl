## Installation steps

### Requirements
You will need Python and `pip` installed on your computer.

### Installation steps for end-users
You can install Owl directly from the [Python Package Index](http://pypi.org).
The following command will install the current version of owlplanner and all its dependencies:
```shell
pip install -r ui/requirements.txt
```

### Installation steps for developers
You will need the latest version of Owl.
```shell
git clone https://github.com/mdlacasse/Owl.git

```
Open a command line terminal and `cd` to the directory where you installed Owl.
From the top directory after downloading run:
```shell
python -m build 
pip install -e .
```
The -e instruct to use the version under the development tree. 
### Running the streamlit frontend 
Running Owl locally from Windows:
```shell
./owlplanner.cmd
```
From Linux or MacOS:
```shell
./owlplanner.sh
```

### Publishing a version (for reference only)
Edit version number in `src/owlplanner/version.py`, `ui/requirements.txt`, and in `pyproject.toml`. Then,
```shell
rm dist/*
python -m build
twine upload --repository [repo] dist/*
```
where [repo] is *testpypi* or *pypi* depending on the type of release.
