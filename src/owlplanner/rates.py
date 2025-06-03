"""

Owl/rates
---

A retirement planner using linear programming optimization.

See companion document for a complete explanation and description
of all variables and parameters.

This class provides the historical annual rate of returns for different
classes of assets: S&P500, Aaa and Baa corporate bonds, 3-mo T-Bills,
10-year Treasury notes, and inflation as measured by CPI all from
1928 until now.

Values were extracted from NYU's Stern School of business:
https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html
from references therein.

Rate lists will need to be updated with values for current year.
When doing so, the TO bound defined below will need to be adjusted
to the last current data year.

Copyright &copy; 2024 - Martin-D. Lacasse

Disclaimers: This code is for educatonal purposes only and does not constitute financial advice.

"""

###################################################################
import numpy as np
import pandas as pd
import os
import sys
from datetime import date

from owlplanner import mylogging as log
from owlplanner import utils as u

# All data goes from 1928 to 2024. Update the TO value when data
# becomes available for subsequent years.
FROM = 1928
TO = 2024

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

# Annual rate of return (%) of Aaa Corporate Bonds since 1928.
BondsAaa = df["Bonds Aaa"]

# Annual rate of return (%) for 10-y Treasury notes since 1928.
TNotes = df["TNotes"]

# Annual rates of return for 3-month Treasury bills since 1928.
TBills = df["TBills"]

# Inflation rate as U.S. CPI index (%) since 1928.
Inflation = df["Inflation"]


def getRatesDistributions(frm, to, mylog=None):
    """
    Pre-compute normal distribution parameters for the series above.
    This calculation takes into account the correlations between
    the different rates. Function returns means and covariance matrix.
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
        "SP500": SP500,
        "BondsBaa": BondsBaa,
        "T. Notes": TNotes,
        "Inflation": Inflation,
    }

    df = pd.DataFrame(series)
    df = df.truncate(before=frm, after=to)

    means = df.mean()
    stdev = df.std()
    covar = df.cov()

    mylog.print("means: (%)\n", means)
    mylog.print("standard deviation: (%)\n", stdev)

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
    mylog.print("correlation matrix: \n\t\t%s" % str(corr).replace("\n", "\n\t\t"))

    return means, stdev, corr, covar


def historicalValue(amount, year):
    """
    Return the deflated value of amount given in this year's dollars as
    valued at the beginning of the year specified.
    """
    thisyear = date.today().year
    if TO != thisyear - 1:
        raise RuntimeError(f"Rates file needs to be updated to be current to {thisyear}.")
    if year < FROM:
        raise ValueError(f"Only data from {FROM} is available.")
    if year > thisyear:
        raise ValueError(f"Year must be < {thisyear} for historical data.")

    span = thisyear - year
    ub = len(Inflation)
    for n in range(ub - span, ub):
        amount /= 1 + Inflation[n] / 100

    return amount


class Rates(object):
    """
    Rates are stored in a 4-array in the following order:
    Stocks, Bonds, Fixed assets, and Inflation.
    Rate are stored in decimal, but the API is in percent.

    To use this class first build an object:
    ``r = Rates()``
    then ``r.setMethod(...)``
    then ``mySeries = r.genSeries()``
    """

    def __init__(self, mylog=None):
        """
        Default constructor.
        """
        if mylog is None:
            self.mylog = log.Logger()
        else:
            self.mylog = mylog

        # Default rates are average over last 30 years.
        self._defRates = np.array([0.1101, 0.0736, 0.0503, 0.0251])

        # Realistic rates are average predictions of major firms
        # as reported by MorningStar in 2023.
        self._optimisticRates = np.array([0.086, 0.049, 0.033, 0.025])

        # Conservative rates.
        self._conservRates = np.array([0.06, 0.04, 0.033, 0.028])

        self.means = np.zeros((4))
        self.stdev = np.zeros((4))
        self.corr = np.zeros((4, 4))
        self.covar = np.zeros((4, 4))

        self.frm = FROM
        self.to = TO

        # Default values for rates.
        self.setMethod("default")

    def setMethod(self, method, frm=None, to=TO, values=None, stdev=None, corr=None):
        """
        Select the method to generate the annual rates of return
        for the different classes of assets.  Different methods include:
        - default:  average over last 30 years.
        - optimistic: predictions from various firms reported by MorningStar.
        - conservative: conservative values.
        - user: user-selected fixed rates.
        - historical: historical rates from 1928 to last year.
        - historical average or means: average over historical data.
        - histochastic: randomly generated from the statistical properties of a historical range.
        - stochastic: randomly generated from means, standard deviation and optionally a correlation matrix.
        The correlation matrix can be provided as a full matrix or
        by only specifying the off-diagonal elements as a simple list
        of (Nk*Nk - Nk)/2 values for Nk assets.
        For 4 assets, this represents a list of 6 off-diagonal values.
        """
        if method not in [
            "default",
            "optimistic",
            "conservative",
            "user",
            "historical",
            "historical average",
            "mean",
            "stochastic",
            "histochastic",
        ]:
            raise ValueError(f"Unknown rate selection method {method}.")

        Nk = len(self._defRates)
        # First process fixed methods relying on values.
        if method == "default":
            self.means = self._defRates
            # self.mylog.vprint('Using default fixed rates values:', *[u.pc(k) for k in values])
            self._setFixedRates(self._defRates)
        elif method == "optimistic":
            self.means = self._defRates
            self.mylog.vprint("Using optimistic fixed rates values:", *[u.pc(k) for k in self.means])
            self._setFixedRates(self._optimisticRates)
        elif method == "conservative":
            self.means = self._conservRates
            self.mylog.vprint("Using conservative fixed rates values:", *[u.pc(k) for k in self.means])
            self._setFixedRates(self._conservRates)
        elif method == "user":
            if values is None:
                raise ValueError("Fixed values must be provided with the user option.")
            if len(values) != Nk:
                raise ValueError(f"Values must have {Nk} items.")
            self.means = np.array(values, dtype=float)
            # Convert percent to decimal for storing.
            self.means /= 100.0
            self.mylog.vprint("Setting rates using fixed user values:", *[u.pc(k) for k in self.means])
            self._setFixedRates(self.means)
        elif method == "stochastic":
            if values is None:
                raise ValueError("Mean values must be provided with the stochastic option.")
            if stdev is None:
                raise ValueError("Standard deviations must be provided with the stochastic option.")
            if len(values) != Nk:
                raise ValueError(f"Values must have {Nk} items.")
            if len(stdev) != Nk:
                raise ValueError(f"stdev must have {Nk} items.")
            self.means = np.array(values, dtype=float)
            self.stdev = np.array(stdev, dtype=float)
            # Convert percent to decimal for storing.
            self.means /= 100.0
            self.stdev /= 100.0
            # Build covariance matrix from standard deviation and correlation matrix.
            if corr is None:
                corrarr = np.identity(Nk)
            else:
                corrarr = np.array(corr)
                # Full correlation matrix was provided.
                if corrarr.shape == (Nk, Nk):
                    pass
                # Only off-diagonal elements were provided: build full matrix.
                elif corrarr.shape == ((Nk * Nk - Nk) / 2,):
                    newcorr = np.identity(Nk)
                    x = 0
                    for i in range(Nk):
                        for j in range(i + 1, Nk):
                            newcorr[i, j] = corrarr[x]
                            newcorr[j, i] = corrarr[x]
                            x += 1
                    corrarr = newcorr
                else:
                    raise RuntimeError(f"Unable to process correlation shape of {corrarr.shape}.")

            self.corr = corrarr
            if not np.array_equal(self.corr, self.corr.T):
                raise ValueError("Correlation matrix must be symmetric.")
            # Now build covariance matrix from stdev and correlation matrix.
            # Multiply each row by a vector element-wise. Then columns.
            covar = self.corr * self.stdev
            self.covar = covar.T * self.stdev
            self._rateMethod = self._stochRates
            self.mylog.vprint("Setting rates using stochastic method with means:", *[u.pc(k) for k in self.means])
            self.mylog.vprint("\t standard deviations:", *[u.pc(k) for k in self.stdev])
            self.mylog.vprint("\t and correlation matrix:\n\t\t", str(self.corr).replace("\n", "\n\t\t"))
        else:
            # Then methods relying on historical data range.
            if frm is None:
                raise ValueError("From year must be provided with this option.")
            if not (FROM <= frm <= TO):
                raise ValueError(f"Lower range 'frm={frm}' out of bounds.")
            if not (FROM <= to <= TO):
                raise ValueError(f"Upper range 'to={to}' out of bounds.")
            if not (frm < to):
                raise ValueError("Unacceptable range.")
            self.frm = frm
            self.to = to

            if method == "historical":
                self.mylog.vprint(f"Using historical rates representing data from {frm} to {to}.")
                self._rateMethod = self._histRates
            elif method == "historical average" or method == "means":
                self.mylog.vprint(f"Using average of rates from {frm} to {to}.")
                self.means, self.stdev, self.corr, self.covar = getRatesDistributions(frm, to, self.mylog)
                self._setFixedRates(self.means)
            elif method == "histochastic":
                self.mylog.vprint(f"Using histochastic rates derived from years {frm} to {to}.")
                self._rateMethod = self._stochRates
                self.means, self.stdev, self.corr, self.covar = getRatesDistributions(frm, to, self.mylog)
            else:
                raise ValueError(f"Method {method} not supported.")

        self.method = method

        return self.means, self.stdev, self.corr

    def _setFixedRates(self, rates):
        Nk = len(self._defRates)
        if len(rates) != Nk:
            raise ValueError(f"Rate list provided must have {Nk} entries.")
        self._myRates = np.array(rates)
        self._rateMethod = self._fixedRates

        return

    def genSeries(self, N):
        """
        Generate a series of Nx4 entries of rates representing S&P500,
        corporate Baa bonds, 10-y treasury notes, and inflation,
        respectively. If there are less than 'N' entries
        in sub-series selected by 'setMethod()', values will be repeated
        modulo the length of the sub-series.
        """
        rateSeries = np.zeros((N, 4))

        # Convert years to indices.
        ifrm = self.frm - FROM
        ito = self.to - FROM

        # Add one since bounds are inclusive.
        span = ito - ifrm + 1

        # Assign 4 values at the time.
        for n in range(N):
            rateSeries[n][:] = self._rateMethod((ifrm + (n % span)))[:]

        return rateSeries

    def _fixedRates(self, n):
        """
        Return rates provided.
        For fixed rates, values are time-independent, and therefore
        the 'n' argument is ignored.
        """
        # Fixed rates are stored in decimal.
        return self._myRates

    def _histRates(self, n):
        """
        Return a list of 4 values representing the historical rates
        of stock, Corporate Baa bonds, Treasury notes, and inflation,
        respectively.
        """
        hrates = np.array([SP500[n], BondsBaa[n], TNotes[n], Inflation[n]])

        # Convert from percent to decimal.
        return hrates / 100

    def _stochRates(self, n):
        """
        Return a list of 4 values representing the historical rates
        of stock, Corporate Baa bonds, Treasury notes, and inflation,
        respectively. Values are pulled from normal distributions
        having the same characteristics as the historical data for
        the range of years selected. Argument 'n' is ignored.

        But these variables need to be looked at together
        through multivariate analysis. Code below accounts for
        covariance between stocks, bonds, and inflation.
        """
        srates = np.random.multivariate_normal(self.means, self.covar)

        return srates
