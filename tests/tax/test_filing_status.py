"""
Tests for tax_federal.filingStatusIndex_n, the rule that a couple files jointly through the year of
the first death and single after, as an index into the [single, MFJ] tables. It is read by the
federal brackets (taxBrackets), the gains tax (capitalGainTax and the LTCG rows), the NIIT
(computeNIIT and its rows), the taxability of Social Security (and its rows), the payroll tax and
the state brackets (tax_state.st_taxParams); the plans that pin those to the cent elsewhere in the
suite check that nothing moved. taxParams and seniorBonusSchedule keep their own copy, next to the
list of who is alive that the same death changes.

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

import numpy as np
import pytest

from owlplanner import tax_federal as tx


@pytest.mark.parametrize(
    "N_i, n_d, expected",
    [
        (2, 2, [1, 1, 0, 0]),
        (2, 0, [0, 0, 0, 0]),
        (2, 4, [1, 1, 1, 1]),
        (2, 9, [1, 1, 1, 1]),
        (2, None, [1, 1, 1, 1]),
        (1, 4, [0, 0, 0, 0]),
        (1, 2, [0, 0, 0, 0]),
    ],
)
def test_filing_status_n(N_i, n_d, expected):
    assert tx.filingStatusIndex_n(N_i, n_d, 4).tolist() == expected


def _niit_loop(N_i, MAGI_n, I_n, Q_n, n_d, N_n):
    """computeNIIT as it was written before it read filingStatusIndex_n: the reference."""
    J_n = np.zeros(N_n)
    status = N_i - 1
    for n in range(N_n):
        if status and n == n_d:
            status -= 1
        Gmax = tx.niitThreshold[status]
        if MAGI_n[n] > Gmax:
            J_n[n] = tx.niitRate * min(MAGI_n[n] - Gmax, I_n[n] + Q_n[n])
    return J_n


@pytest.mark.parametrize("seed", range(20))
def test_compute_niit_equals_the_loop(seed):
    rng = np.random.default_rng(seed)
    N_n = int(rng.integers(1, 40))
    N_i = int(rng.integers(1, 3))
    n_d = int(rng.integers(0, N_n + 1)) if N_i == 2 else N_n
    MAGI_n = rng.uniform(0, 600_000, N_n)
    MAGI_n[rng.random(N_n) < 0.2] = 250_000.0  # at the threshold: no tax
    I_n = rng.uniform(0, 80_000, N_n)
    Q_n = rng.uniform(-20_000, 120_000, N_n)
    np.testing.assert_array_equal(tx.computeNIIT(N_i, MAGI_n, I_n, Q_n, n_d, N_n),
                                  _niit_loop(N_i, MAGI_n, I_n, Q_n, n_d, N_n))
