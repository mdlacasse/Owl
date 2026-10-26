<!--
Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
SPDX-License-Identifier: CC-BY-NC-SA-4.0
This documentation is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0; see LICENSE-docs in the repository root.
-->

# Owl - Optimal wealth lab

## A retirement exploration tool based on mixed-integer linear programming

<img align=right src="https://github.com/mdlacasse/Owl/blob/main/assets/owl.png?raw=true" width="350">

------------------------------------------------------------------------------------

### About
This document is aimed at software developers desiring to install the Owl source code
and run it locally on their computer.

For end-users, we suggest accessing Owl from the
[Streamlit Community Cloud](https://owlplanner.streamlit.app)
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

Use this path if you prefer to manage your own Python environment. Owl requires Python 3.11 or later.

#### Creating a virtual environment

**Anaconda** ([download](https://repo.anaconda.com/archive/)):
```shell
conda create --name owlenv python=3.12
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
The `owlplanner.sh` and `owlplanner.cmd` scripts launch Owl through `uv`, which would build its own
environment instead of using yours. From the activated environment, start Streamlit directly:
```shell
streamlit run ui/main.py
```
The scripts add `--browser.gatherUsageStats=false --browser.serverAddress=localhost --server.fileWatcherType=auto`,
which can be appended to the same command.

---

### Developer setup

Clone the repository and install in editable mode so changes to the source are
reflected immediately without reinstalling.

**With uv** (`uv sync` installs Owl in editable mode, with the `dev` tools):
```shell
uv sync
uv sync --extra notebooks          # optional: add Jupyter
```
Add `--extra notebooks` to later `uv sync` commands too, as a plain `uv sync` removes what the lockfile
does not list.

**With pip:**
```shell
pip install -e .
pip install -e ".[notebooks]"      # optional: add Jupyter
```

---

### Publishing a release (maintainers only)
Assuming N processors as NPROC
(using less than actual number avoid memory bandwidth saturation):

Run checks before all commits:
```shell
flake8 ui src tests
make tests
```
`make tests` runs the whole suite twice, with MOSEK and then with HiGHS. `make tests-deep` adds
the slow quality checks left out of the default run, worth running when changing an algorithm.
A plain `uv run pytest -n $NPROC` runs HiGHS only, as an unset `OWL_TEST_SOLVER` pins it.

On macOS / Linux, to test against one solver:
```shell
OWL_TEST_SOLVER="HiGHS" uv run pytest -n $NPROC
OWL_TEST_SOLVER="MOSEK" uv run pytest -n $NPROC
```

On Windows (PowerShell):
```powershell
$env:OWL_TEST_SOLVER="HiGHS" ; uv run pytest -n $NPROC
$env:OWL_TEST_SOLVER="MOSEK" ; uv run pytest -n $NPROC
```

Bump the version in `pyproject.toml` (`[project].version`, the single source of
truth), then sync the mirrored copy in `src/owlplanner/version.py`, upgrade every dependency
in `uv.lock`, and regenerate `requirements.txt`:
```shell
make update
```
`make outdated` lists what the upgrade would change without changing anything, and
`make sync-version` syncs `version.py` alone.

Then build and publish the package to PyPI by running `./buildPackage.sh` from the `docker/`
directory (or `buildPackage.cmd` on Windows), as the script starts with `cd ..`. It removes old `dist/` artifacts and runs
`uv build` followed by `uv publish`, picking up the PyPI token from `~/.pypirc`.
