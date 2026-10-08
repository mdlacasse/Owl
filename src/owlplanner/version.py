"""
Package version information.

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

import subprocess
from functools import lru_cache
from pathlib import Path

__version__ = "2026.10.9"


@lru_cache(maxsize=1)
def engine_commit():
    """Short git commit of the source tree this package runs from, or None.

    Suffixed "-dirty" when tracked files differ from that commit. None outside a git
    checkout, and also when this file is not tracked there -- an installed copy sitting in
    a virtualenv inside some repository must not report that repository's commit.
    """
    here = Path(__file__).resolve().parent

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(here), *args], capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()

    try:
        git("ls-files", "--error-unmatch", Path(__file__).name)
        sha = git("rev-parse", "--short", "HEAD")
        dirty = git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{sha}-dirty" if dirty else sha


def engine_provenance():
    """Identify the engine that produced a result: {"version": ..., "commit": ... or None}."""
    return {"version": __version__, "commit": engine_commit()}
