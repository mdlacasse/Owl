"""
Test that the package version stays in sync across its two locations.

`pyproject.toml` `[project].version` is the single source of truth; the literal
in `src/owlplanner/version.py` is a generated mirror (run `make sync-version`).
This test fails the build whenever the two drift apart.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import pathlib
import tomllib

from owlplanner import __version__

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_version_matches_pyproject():
    pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
    expected = pyproject["project"]["version"]
    assert __version__ == expected, (
        f"version mismatch: pyproject.toml has {expected!r} but owlplanner.__version__ "
        f"is {__version__!r}. Run `make sync-version` to regenerate src/owlplanner/version.py."
    )
