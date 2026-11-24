"""
_bound_key must classify bounds exactly as it did when it called np.isclose.

The scalar test was rewritten in plain Python for speed, and np.isclose is not
math.isclose: its tolerances are looser (rtol=1e-5, atol=1e-8), it measures the
relative part against the second argument only, and it treats a matching pair of
infinities as close. The reference below is the original implementation.

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

import itertools

import numpy as np
import pytest

from owlplanner.abcapi import _bound_key, _isclose

inf = np.inf


def _reference_key(lb, ub):
    if np.isclose(lb, ub):
        return "fx"
    elif ub == inf and lb == -inf:
        return "fr"
    elif ub == inf:
        return "lo"
    elif lb == -inf:
        return "up"
    else:
        return "ra"


@pytest.mark.parametrize(
    "lb, ub, key",
    [
        (0, inf, "lo"),
        (-inf, 0, "up"),
        (-inf, inf, "fr"),
        (inf, inf, "fx"),
        (-inf, -inf, "fx"),
        (3, 3, "fx"),
        (0, 5, "ra"),
        (0, 1e-9, "fx"),  # within atol
        (1e5, 1e5 + 0.5, "fx"),  # within rtol of ub
        (1e5, 1e5 + 2.0, "ra"),  # outside rtol of ub
        (0, 2e-8, "ra"),  # just outside atol
        (-1.0, -1.0 + 5e-6, "fx"),  # negative side, within rtol
    ],
)
def test_bound_key_pinned_cases(lb, ub, key):
    assert _bound_key(lb, ub) == key
    assert _reference_key(lb, ub) == key


# The relative tolerance is measured against the second argument, so a pair that is
# close one way round can fail the other way round.
def test_isclose_is_asymmetric_like_numpy():
    a, b = 1e5 + 1.000005, 1e5
    assert _isclose(a, b) == bool(np.isclose(a, b))
    assert _isclose(b, a) == bool(np.isclose(b, a))
    assert _isclose(a, b) != _isclose(b, a)


_VALUES = [
    -inf, -1e12, -1e5, -1.0, -1e-6, -1e-9, 0.0, 1e-9, 2e-8, 1e-6, 0.5, 1.0, 1.0 + 1e-6, 1.0 + 5e-5,
    1e5, 1e5 + 0.5, 1e5 + 1.5, 1e12, 1e12 + 1e6, 1e12 + 5e7, inf, np.float64(3.0), 3,
]


@pytest.mark.parametrize("lb, ub", list(itertools.product(_VALUES, _VALUES)))
def test_bound_key_matches_numpy_reference(lb, ub):
    assert _bound_key(lb, ub) == _reference_key(lb, ub)
    assert _isclose(lb, ub) == bool(np.isclose(lb, ub))


def test_isclose_on_nan_is_false_like_numpy():
    assert _isclose(np.nan, np.nan) is False
    assert _isclose(1.0, np.nan) is False
