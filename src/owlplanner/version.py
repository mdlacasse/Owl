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

__version__ = "2026.11.26"


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


# The inputs that define WHICH HOUSEHOLD a result is about. Hashed into every artifact by
# case_provenance() below, because the engine commit alone provably cannot identify a run: on
# 2026-11-25 an audit of 93 Cost_of_Committing artifacts found 26 run with a taxable cost basis
# and 31 without, 36 of them unclassifiable, because taxable_cost_basis sat UNCOMMITTED in the
# case files for weeks. Adding it moved one reference conversion by -38.5%. A clean engine stamp
# said nothing about it, and the only surviving trace was the "-dirty" suffix.
#
# Adding a field here changes every hash and so invalidates comparisons across the change; that
# is the intended behaviour, and the reason the list is short and limited to inputs.
CASE_INPUT_FIELDS = (
    "inames",           # who
    "yobs", "mobs", "tobs", "expectancy", "horizons",
    "beta_ij",          # opening balances per account
    "taxable_basis_i",  # the cost basis: the field this mechanism exists for
    "nu",               # heirs' tax rate
    "chi",              # survivor fraction
    "state",            # state income tax
    "zetaBar_in",       # spending profile
    "pi_in",            # Social Security
    "myRothX_in", "rothXfixed_in",  # the Roth pins: amount and whether each binds
)


def case_provenance(*plans):
    """A short hash of the case inputs of each plan: {"cases": {name: sha12}, "fields": n}.

    Identifies the household a result is about, independently of the engine that produced it.
    Values are canonicalized through repr() of numpy-or-scalar content, so a float that reads
    back identically hashes identically. A field a plan does not carry is recorded as absent
    rather than skipped, so two plans differing only in which fields exist hash differently.
    """
    import hashlib

    out = {}
    for plan in plans:
        parts = []
        for f in CASE_INPUT_FIELDS:
            v = getattr(plan, f, None)
            if v is None:
                parts.append(f + "=<absent>")
                continue
            arr = getattr(v, "tolist", None)
            parts.append(f + "=" + repr(arr() if callable(arr) else v))
        blob = "\n".join(parts).encode("utf-8")
        name = getattr(plan, "_name", None) or getattr(plan, "name", None) or "plan"
        out[str(name)] = hashlib.sha256(blob).hexdigest()[:12]
    return {"cases": out, "fields": len(CASE_INPUT_FIELDS)}


def run_provenance(*plans, pubs_dir=None):
    """Everything needed to identify a run: engine, case hashes, and the paper repo's commit.

    pubs_dir names a second checkout -- the scripts and artifacts that drove the run, which for
    Cost_of_Committing live in their own repository -- so an artifact records both halves and
    neither has to be guessed later.
    """
    prov = {"engine": engine_provenance()}
    if plans:
        prov.update(case_provenance(*plans))
    if pubs_dir:
        try:
            r = subprocess.run(
                ["git", "-C", str(pubs_dir), "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5, check=True)
            d = subprocess.run(
                ["git", "-C", str(pubs_dir), "status", "--porcelain", "--untracked-files=no"],
                capture_output=True, text=True, timeout=5, check=True).stdout.strip()
            sha = r.stdout.strip()
            prov["pubs_commit"] = f"{sha}-dirty" if d else sha
        except (OSError, subprocess.SubprocessError):
            prov["pubs_commit"] = None
    return prov
