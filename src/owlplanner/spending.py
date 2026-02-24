"""
Spending profile generation utilities.

This module implements spending profile time series: flat and smile (retirement
spending) profiles, with survivor fraction and normalization.

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


def gen_spending_profile(profile, fraction, n_d, N_n, dip=15, increase=12, delay=0):
    """
    Generate spending profile time series.

    Value is reduced to fraction starting in year n_d (after passing of
    shortest-lived spouse). Series is unadjusted for inflation.

    Parameters
    ----------
    profile : str
        'flat' or 'smile'
    fraction : float
        Survivor fraction (0–1) applied from year n_d onward
    n_d : int
        Year index when survivor reduction begins
    N_n : int
        Plan horizon (number of years)
    dip : float
        Percent dip for smile profile (cosine amplitude)
    increase : float
        Percent linear increase for smile profile
    delay : int
        Years to delay before smile curve starts

    Returns
    -------
    xi : ndarray
        Length N_n, spending profile unadjusted for inflation
    """
    xi = np.ones(N_n)
    if profile == "flat":
        if n_d < N_n:
            xi[n_d:] *= fraction
    elif profile == "smile":
        span = N_n - 1 - delay
        x = np.linspace(0, span, N_n - delay)
        a = dip / 100
        b = increase / 100
        xi[delay:] = xi[delay:] + a * np.cos((2 * np.pi / span) * x) + (b / (N_n - 1)) * x
        xi[:delay] = xi[delay]
        neutralSum = N_n
        if n_d < N_n:
            neutralSum -= (1 - fraction) * (N_n - n_d)
            xi[n_d:] *= fraction
        xi *= neutralSum / xi.sum()
    else:
        raise ValueError(f"Unknown profile type '{profile}'.")

    return xi
