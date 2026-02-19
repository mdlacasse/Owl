"""
Historical and statistical rate of return data for asset classes.

This module provides historical annual rates of return for different asset
classes: S&P 500, Baa corporate bonds, real estate, 3-mo T-Bills, 10-year Treasury
notes, and inflation as measured by CPI from 1928 to present. Values were
extracted from NYU's Stern School of business historical returns data.

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

###################################################################
import numpy as np
import pandas as pd
import os
import sys

from owlplanner import mylogging as log

# All data goes from 1928 to 2025. Update the TO value when data
# becomes available for subsequent years.
FROM = 1928
TO = 2025

# Canonical fixed rates (decimal). Single source of truth for UI/config sync.
_DEF_RATES = np.array([0.1101, 0.0736, 0.0503, 0.0251])   # 30-year trailing avg
_OPTIMISTIC_RATES = np.array([0.086, 0.049, 0.033, 0.025])  # MorningStar 2023
_CONSERV_RATES = np.array([0.06, 0.04, 0.033, 0.028])


def get_fixed_rate_values(method):
    """
    Return the canonical fixed rate values (percent) for built-in methods.

    Single source of truth for conservative, optimistic, and default rates.
    Used by the UI and config-to-plan bridge to avoid duplication and sync drift.

    Args:
        method: One of "conservative", "optimistic", "default"

    Returns:
        List of 4 floats in percent: [S&P 500, Bonds Baa, T-Notes, Inflation]

    Raises:
        ValueError: If method is not a supported fixed method.
    """
    if method == "default":
        arr = _DEF_RATES
    elif method == "optimistic":
        arr = _OPTIMISTIC_RATES
    elif method == "conservative":
        arr = _CONSERV_RATES
    else:
        raise ValueError(f"Unknown fixed rate method '{method}'.")
    return [float(100 * x) for x in arr]


def get_fixed_rates_decimal(method):
    """
    Return canonical fixed rate values (decimal) for built-in methods.

    Single source of truth for conservative, optimistic, and default rates.
    Used by BuiltinRateModel and _builtin_impl.

    Args:
        method: One of "conservative", "optimistic", "default"

    Returns:
        Array of 4 floats in decimal (0.07 = 7%)

    Raises:
        ValueError: If method is not a supported fixed method.
    """
    if method == "default":
        return _DEF_RATES.copy()
    if method == "optimistic":
        return _OPTIMISTIC_RATES.copy()
    if method == "conservative":
        return _CONSERV_RATES.copy()
    raise ValueError(f"Unknown fixed rate method '{method}'.")


where = os.path.dirname(sys.modules["owlplanner"].__file__)
file = os.path.join(where, "data/rates.csv")
try:
    df = pd.read_csv(file)
except Exception as e:
    raise RuntimeError(f"Could not find rates data file: {e}") from e


# Annual rate of return (%) of S&P 500 since 1928, including dividends.
SP500 = df["S&P 500"]

# Annual rate of return (%) of Baa Corporate Bonds since 1928.
BondsBaa = df["Bonds Baa"]

# Annual rate of return (%) of Real Estate since 1928.
RealEstate = df["real estate"]

# Annual rate of return (%) for 10-y Treasury notes since 1928.
TNotes = df["TNotes"]

# Annual rates of return for 3-month Treasury bills since 1928.
TBills = df["TBills"]

# Inflation rate as U.S. CPI index (%) since 1928.
Inflation = df["Inflation"]


def getRatesDistributions(frm, to, mylog=None, in_percent=True):
    """
    Pre-compute normal distribution parameters for the series above.
    This calculation takes into account the correlations between
    the different rates. Function returns means, stdev, correlation matrix,
    and covariance matrix.

    By default (in_percent=True), means and stdev are returned in percent
    (e.g. 7.0 = 7%), matching the units expected by setRates(). Pass
    in_percent=False to get decimal values (e.g. 0.07 = 7%) suitable for
    direct NumPy math. The correlation and covariance matrices are always
    returned in their natural (decimal) form and are never converted.

    Parameters
    ----------
    frm : int
        Start year (inclusive).
    to : int
        End year (inclusive).
    mylog : Logger, optional
        Logger instance; a default silent logger is used if None.
    in_percent : bool, optional
        If True (default), return means/stdev in percent (e.g. 7.0 = 7%).
        If False, return means/stdev in decimal (e.g. 0.07 = 7%).
        corr and covar are unaffected.
    """
    if mylog is None:
        mylog = log.Logger()

    # Convert years to index and check range.
    frm -= FROM
    to -= FROM
    if not (0 <= frm and frm <= len(SP500)):
        raise ValueError(f"Range 'from' {frm} out of bounds.")
    if not (0 <= to and to <= len(SP500)):
        raise ValueError(f"Range 'to' {to} out of bounds.")
    if frm >= to:
        raise ValueError(f'"from" {frm} must be smaller than "to" {to}.')

    series = {
        "S&P 500": SP500,
        "Bonds Baa": BondsBaa,
        "T-Notes": TNotes,
        "Inflation": Inflation,
    }

    df = pd.DataFrame(series)
    df = df.truncate(before=frm, after=to)

    means = df.mean()
    stdev = df.std()
    covar = df.cov()

    mylog.vprint("means: (%)\n", means)
    mylog.vprint("standard deviation: (%)\n", stdev)

    # Convert to NumPy array and from percent to decimal.
    means = np.array(means) / 100.0
    stdev = np.array(stdev) / 100.0
    covar = np.array(covar) / 10000.0
    # Build correlation matrix by dividing by the stdev for each column and row.
    corr = covar / stdev[:, None]
    corr = corr.T / stdev[:, None]
    # Fold round-off errors in proper bounds.
    corr[corr > 1] = 1
    corr[corr < -1] = -1
    mylog.vprint("correlation matrix: \n\t\t%s" % str(corr).replace("\n", "\n\t\t"))

    if in_percent:
        means = means * 100
        stdev = stdev * 100
    # corr and covar are correlation-derived (unitless or decimal); never converted
    return means, stdev, corr, covar
