### Installation steps

#### Requirements
You will need Python and `pip` installed on your computer.

### Installation steps for end-users
The following command will install the latest published version of owlplanner and all its dependencies:
``` shell
pip install -r ui/requirements.txt
```

### Installation steps for developers
Open a command line terminal and `cd` to the directory where you installed Owl.
From the top directory after downloading run:
``` shell
python -m build 
pip install -e .
```

### Running the streamlit frontend 
Just run the script:
```shell
owlplanner.cmd
```

### Publishing a version (for reference)
Edit version and data in pyproject.toml. Then,
``` shell
rm dist
python -m build
twine upload --repository testpypi dist/*
```
