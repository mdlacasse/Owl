"""
Pytest configuration and shared fixtures.

Freezes date.today() to 2026-01-01 across all owlplanner source modules and
test modules so that tests are immune to calendar year rollover.  When the
project is deliberately advanced to a new tax year, update _FROZEN_DATE below,
increment birth years in examples/*.toml, and refresh the expected values in
test_toml_cases.py.
"""

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
def freeze_year():
    """
    Replace date.today() with a fixed date for the entire test session.

    Scans sys.modules for every already-imported module whose 'date' attribute
    is the real datetime.date class and patches it with _FixedDate.  This
    covers both owlplanner source modules and test modules without needing a
    hardcoded list of names.
    """
    target_modules = [
        mod for mod in sys.modules.values()
        if mod is not None and getattr(mod, "date", None) is _REAL_DATE
    ]
    patches = [patch.object(mod, "date", _FixedDate) for mod in target_modules]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()
