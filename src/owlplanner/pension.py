"""
Pension benefit calculation and timing utilities.

This module implements pension benefit timing rules: when pension payments
start based on commencement age and birth month, with fractional first-year
adjustment.

Copyright (C) 2025-2026 The Owlplanner Authors

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
from datetime import date


def compute_pension_benefits(amounts, ages, yobs, mobs, horizons, N_i, N_n, thisyear=None):
    """
    Compute annual pension benefits by individual and year.

    Pension amounts are monthly; output is annual (×12). Timing uses age + birth
    month to determine start year, with fractional first-year proration.

    Parameters
    ----------
    amounts : array
        Monthly pension amounts per individual
    ages : array
        Commencement ages per individual
    yobs : array
        Birth years per individual
    mobs : array
        Birth months (1-12) per individual
    horizons : array
        Year index when each individual's horizon ends
    N_i : int
        Number of individuals
    N_n : int
        Plan horizon (number of years)
    thisyear : int or None
        Current calendar year (default: date.today().year)

    Returns
    -------
    pi_in : ndarray
        Shape (N_i, N_n), annual pension benefits per individual per year
    """
    if thisyear is None:
        thisyear = date.today().year

    amounts = np.asarray(amounts, dtype=np.float64)
    ages = np.asarray(ages, dtype=np.float64)

    pi_in = np.zeros((N_i, N_n))
    for i in range(N_i):
        if amounts[i] != 0:
            yearage = ages[i] + (mobs[i] - 1) / 12
            iage = int(yearage)
            fraction = 1 - (yearage % 1.0)
            realns = iage - thisyear + yobs[i]
            ns = max(0, realns)
            nd = horizons[i]
            pi_in[i, ns:nd] = amounts[i]
            if realns >= 0:
                pi_in[i, ns] *= fraction

    pi_in *= 12
    return pi_in
