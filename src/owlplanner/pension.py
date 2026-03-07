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
    yobs = np.asarray(yobs, dtype=int)
    mobs = np.asarray(mobs, dtype=int)
    horizons = np.asarray(horizons, dtype=int)

    pi_in = np.zeros((N_i, N_n))
    for i in range(N_i):
        if amounts[i] != 0:
            # Age as fractional year: e.g., age 65, born in July → 65 + 6/12 = 65.5
            age_with_month = ages[i] + (mobs[i] - 1) / 12
            start_age = int(age_with_month)
            # Fraction of first year pension is received (1.0 if born in Jan, ~1/12 if born in Dec)
            first_year_fraction = 1 - (age_with_month % 1.0)
            start_idx_raw = start_age - thisyear + yobs[i]
            start_idx = max(0, start_idx_raw)
            end_idx = horizons[i]
            pi_in[i, start_idx:end_idx] = amounts[i]
            if start_idx_raw >= 0:
                pi_in[i, start_idx] *= first_year_fraction

    pi_in *= 12
    return pi_in


def compute_piBar_in(pi_in, gamma_n, indexed, survivor_fraction, n_d, i_d, i_s,
                     horizons, N_i, N_n):
    """
    Apply inflation scaling and survivor logic to primary pension; return piBar_in.

    Parameters
    ----------
    pi_in : ndarray
        Shape (N_i, N_n), annual pension benefits (primary only)
    gamma_n : ndarray
        Length N_n, cumulative inflation factors
    indexed : list of bool
        Whether each pension is inflation-indexed
    survivor_fraction : array
        Fraction of pension continuing to surviving spouse (0-1) per individual
    n_d : int
        Year index of first death
    i_d : int
        Index of first-to-die individual
    i_s : int
        Index of survivor (-1 if single or same horizon)
    horizons : array
        Year index when each individual's horizon ends
    N_i, N_n : int
        Number of individuals and plan years

    Returns
    -------
    piBar_in : ndarray
        Shape (N_i, N_n), inflation-adjusted pension with survivor benefits
    """
    piBar_in = np.array(pi_in, dtype=np.float64)

    # Apply inflation to each individual's own pension using their indexing flag.
    for i in range(N_i):
        if indexed[i]:
            piBar_in[i] *= gamma_n

    # Add survivor benefit using the primary's pre-inflation amount (pi_in), then
    # apply the primary's indexing so the benefit tracks the same cost-of-living
    # adjustment as the primary's pension.
    if (N_i == 2 and n_d < N_n and i_s >= 0
            and survivor_fraction[i_d] > 0
            and pi_in[i_d, n_d - 1] > 0):
        survivor_raw = survivor_fraction[i_d] * pi_in[i_d, n_d - 1]
        if indexed[i_d]:
            piBar_in[i_s, n_d:horizons[i_s]] += survivor_raw * gamma_n[n_d:horizons[i_s]]
        else:
            piBar_in[i_s, n_d:horizons[i_s]] += survivor_raw

    return piBar_in
