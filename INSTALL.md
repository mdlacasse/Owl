# Owl - Optimal wealth lab

## A retirement exploration tool based on mixed-integer linear programming

<img align=right src="https://github.com/mdlacasse/Owl/blob/main/papers/images/owl.png?raw=true" width="250">

------------------------------------------------------------------------------------
### About
This document is aimed at software developers desiring to install the Owl source code
and run it locally on their computer.

For end-users, we suggest accessing Owl from the
[Streamlit Community Cloud](http://owlplanner.streamlit.app)
or, if one prefers to have everything on their own computer,
to install and run a Docker image as described in these [instructions](docker/README.md).

---

### Recommended: install with uv

[uv](https://docs.astral.sh/uv/) is a fast Python package and project manager that
handles Python versions, virtual environments, and dependencies in one tool.
It is the recommended way to install and run Owl.

You will also need `git`, which is found [here](https://git-scm.com/install/windows)
for Windows, and is included with developer tools on macOS and Linux.

#### 1. Install uv

**macOS / Linux:**
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Full installation options are documented [here](https://docs.astral.sh/uv/getting-started/installation/).

#### 2. Clone the repository
```shell
git clone https://github.com/mdlacasse/Owl.git
cd Owl
```

#### 3. Run Owl

On the first launch, `uv` will automatically create a virtual environment and install
all dependencies. Subsequent launches reuse the existing environment.

```shell
# macOS or Linux
./owlplanner.sh

# Windows
./owlplanner.cmd
```

This will open a tab in your default browser.
Hit **Ctrl-C** in the terminal to stop the server.

#### Keeping Owl up to date
```shell
git pull
uv sync
```

---

### Alternative: install with pip or conda

Use this path if you prefer to manage your own Python environment.

#### Creating a virtual environment

**Anaconda** ([download](https://repo.anaconda.com/archive/)):
```shell
conda create --name owlenv
conda activate owlenv
```

**venv** (standard library):
```shell
python -m venv owlenv

# Activate — macOS / Linux
source ./owlenv/bin/activate

# Activate — Windows (Command Prompt)
.\owlenv\Scripts\activate.bat

# Activate — Windows (PowerShell)
./owlenv/Scripts/activate.ps1
```

#### Install dependencies
```shell
git clone https://github.com/mdlacasse/Owl.git
cd Owl
pip install --upgrade -r requirements.txt
```

To also run the Jupyter notebooks in `notebooks/`:
```shell
pip install -e ".[notebooks]"
```

#### Run Owl
```shell
# macOS or Linux
./owlplanner.sh

# Windows
./owlplanner.cmd
```

---

### Developer setup

Clone the repository and install in editable mode so changes to the source are
reflected immediately without reinstalling.

**With uv:**
```shell
uv sync
uv pip install -e ".[notebooks]"   # optional: add Jupyter
```

**With pip:**
```shell
pip install build
python -m build
pip install -e .
pip install -e ".[notebooks]"      # optional: add Jupyter
```

---

### Publishing a release (maintainers only)

Run checks before all commits:
```shell
flake8 ui src tests
pytest -n auto
```

On macOS / Linux, to test against specific solvers:
```shell
OWL_TEST_SOLVER="HiGHS" pytest -n auto
OWL_TEST_SOLVER="MOSEK" pytest -n auto
```

On Windows (PowerShell):
```powershell
$env:OWL_TEST_SOLVER="HiGHS" ; pytest -n auto
$env:OWL_TEST_SOLVER="MOSEK" ; pytest -n auto
```

Bump the version in `pyproject.toml` (`[project].version`, the single source of
truth), then sync the mirrored copy in `src/owlplanner/version.py` and the lockfile:
```shell
make update
```

Then build and publish the package to PyPI by running `docker/buildPackage.sh`
(or `buildPackage.cmd` on Windows). It removes old `dist/` artifacts and runs
`uv build` followed by `uv publish`, picking up the PyPI token from `~/.pypirc`.
