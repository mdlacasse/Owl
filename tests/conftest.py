"""
Pytest configuration and shared fixtures.

Freezes date.today() to 2026-01-01 across all owlplanner source modules and
test modules so that tests are immune to calendar year rollover.  When the
project is deliberately advanced to a new tax year, update _FROZEN_DATE below,
increment birth years in examples/*.toml, and refresh the expected values in
test_toml_cases.py. If HFP structure changes, run scripts/update_hfp_coverage.py
to sync HSA contributions, Debts, and Fixed Assets in example HFPs.

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

import os
import sys
import datetime
import pytest
from unittest.mock import patch

_REAL_DATE = datetime.date
_FROZEN_DATE = _REAL_DATE(2026, 1, 1)


class _FixedDate(_REAL_DATE):
    """datetime.date subclass whose today() always returns _FROZEN_DATE."""

    @classmethod
    def today(cls):
        return _FROZEN_DATE


@pytest.fixture(autouse=True, scope="session")
def configure_test_solver():
    """
    Honour OWL_TEST_SOLVER env var for every test, including tests that don't
    explicitly pass a solver to plan.solve().  Without this patch the 'default'
    path in plan.py falls back to _mosek_available(), which ignores the env var.
    """
    solver_env = os.environ.get("OWL_TEST_SOLVER", "default").lower()
    if solver_env == "mosek":
        with patch("owlplanner.plan._mosek_available", return_value=True):
            yield
    else:
        # Default (unset / "highs" / "default"): pin HiGHS so the default solver is
        # deterministic regardless of import order. Without this, importing any ui
        # module during the session sets MOSEKLM_LICENSE_FILE (see ui/moseklicense.py)
        # and flips _mosek_available() to True mid-run, silently switching unpinned
        # tests to MOSEK and producing non-reproducible reference values.
        with patch("owlplanner.plan._mosek_available", return_value=False):
            yield


@pytest.fixture(autouse=True, scope="session")
def freeze_year():
    """
    Replace date.today() with a fixed date for the entire test session.

    Scans sys.modules for every already-imported module whose 'date' attribute
    is the real datetime.date class and patches it with _FixedDate.  This
    covers both owlplanner source modules and test modules without needing a
    hardcoded list of names.
    """
    target_modules = [
        mod for mod in sys.modules.values() if mod is not None and getattr(mod, "date", None) is _REAL_DATE
    ]
    patches = [patch.object(mod, "date", _FixedDate) for mod in target_modules]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()
