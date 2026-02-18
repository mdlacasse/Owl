"""
Matplotlib backend implementation for plotting retirement planning results.

This module provides the Matplotlib-based implementation of the plot backend
interface for creating static visualizations of retirement planning data.

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
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as tk
import io
import os

os.environ["JUPYTER_PLATFORM_DIRS"] = "1"

import seaborn as sbn           # Noqa: E402

from .base import PlotBackend   # Noqa: E402
from .. import utils as u       # Noqa: E402
from ..rate_models.constants import HISTORICAL_RANGE_METHODS  # Noqa: E402


class MatplotlibBackend(PlotBackend):
    """Matplotlib implementation of plot backend."""

    def __init__(self):
        """Initialize the matplotlib backend."""
        self.set_plot_style()

    def jupyter_renderer(self, fig):
        pass
        # plt.show()

    def set_plot_style(self):
        """Set the style for all matplotlib plots."""
        plt.rcParams.update({'figure.autolayout': True})
        plt.rcParams.update({'figure.figsize': (6, 4)})
        plt.rcParams.update({'axes.grid': True})
        plt.rcParams.update({'axes.grid.which': 'both'})

    def _line_income_plot(self, x, series, style, title, yformat=r"\$k"):
        """Core line plotter function."""
        fig, ax = plt.subplots()

        for sname in series:
            ax.plot(x, series[sname], label=sname, ls=style[sname])

        ax.legend(loc="upper left", reverse=True, fontsize=8, framealpha=0.3)
        ax.set_title(title)
        ax.set_xlabel("year")
        ax.set_ylabel(yformat)
        ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
        if "k" in yformat:
            ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(x / 1000), ",")))
            # Give range to y values in unindexed flat profiles.
            ymin, ymax = ax.get_ylim()
            if ymax - ymin < 5000:
                ax.set_ylim((ymin * 0.95, ymax * 1.05))

        return fig, ax

    def _stack_plot(self, x, inames, title, irange, series, snames, location, yformat=r"\$k"):
        """Core function for stacked plots."""
        nonzeroSeries = {}
        for sname in snames:
            source_data = series[sname]
            # Check if this is a household-level source (shape (1, N_n) when N_i > 1)
            is_household = source_data.shape[0] == 1 and len(inames) > 1
            if is_household:
                # Show household total once without individual name
                tmp = source_data[0]
                if abs(sum(tmp)) > 1.0:  # Use abs for debts
                    nonzeroSeries[sname] = tmp
            else:
                # Show per individual
                for i in irange:
                    tmp = source_data[i]
                    if abs(sum(tmp)) > 1.0:  # Use abs for debts
                        nonzeroSeries[sname + " " + inames[i]] = tmp

        if len(nonzeroSeries) == 0:
            return None, None

        fig, ax = plt.subplots()

        ax.stackplot(x, nonzeroSeries.values(), labels=nonzeroSeries.keys(), alpha=0.6)
        ax.legend(loc=location, reverse=True, fontsize=8, ncol=2, framealpha=0.5)
        ax.set_title(title)
        ax.set_xlabel("year")
        ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
        if "k" in yformat:
            ax.set_ylabel(yformat)
            ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(x / 1000), ",")))
        elif yformat == "percent":
            ax.set_ylabel("%")
            ax.get_yaxis().set_major_formatter(tk.FuncFormatter(lambda x, p: format(int(100 * x), ",")))
        else:
            raise RuntimeError(f"Unknown yformat: {yformat}.")

        return fig, ax

    def plot_histogram_results(self, objective, df, N, year_n, n_d=None, N_i=1, phi_j=None, log_x=False):
        """Show a histogram of values from historical data or Monte Carlo simulations.

        If log_x is True, use log-spaced bins and a log-scale x-axis (log-normal style).
        Zeros are excluded from the histogram when log_x is True.
        """
        _LOG_FLOOR = 0.001   # $1 in thousands; values below excluded when log_x
        _LOG_NBINS_MAX = 50
        _LOG_NBINS_MIN = 10

        def _log_nbins(n_positive):
            """Data-adaptive number of log bins: between 10 and 50, ~sqrt(n) otherwise."""
            if n_positive <= 0:
                return _LOG_NBINS_MIN
            n_bins = int(np.sqrt(n_positive))
            return max(_LOG_NBINS_MIN, min(_LOG_NBINS_MAX, n_bins))

        def _log_spaced_edges(series, floor=_LOG_FLOOR, n_positive=None):
            """Log-spaced bin edges from positive values >= floor. Returns None if no positive data.
            n_positive: if given, used for adaptive bin count; else derived from series."""
            pos = series.to_numpy(dtype=float)
            pos = pos[(pos >= floor) & np.isfinite(pos)]
            if len(pos) == 0:
                return None
            lo, hi = float(np.min(pos)), float(np.max(pos))
            if lo <= 0 or hi <= 0:
                return None
            num_bins = _log_nbins(n_positive if n_positive is not None else len(pos))
            return np.logspace(np.log10(lo), np.log10(hi), num=num_bins + 1)

        description = io.StringIO()

        pSuccess = u.pc(len(df) / N)
        n_failed = N - len(df)
        print(f"Success rate: {pSuccess} on {N} scenarios.", file=description)
        if n_failed > 0:
            print(f"N failed: {n_failed}", file=description)
        title = f"$N$ = {N}, $P$ = {pSuccess}"
        means = df.mean(axis=0, numeric_only=True)
        medians = df.median(axis=0, numeric_only=True)

        my = 2 * [year_n[-1]]
        if N_i == 2 and n_d is not None and n_d < len(year_n):
            my[0] = year_n[n_d - 1]

        # Don't show partial bequest of zero if spouse is full beneficiary,
        # or if solution led to empty accounts at the end of first spouse's life.
        if (phi_j is not None and np.all((1 - phi_j) < 0.01)) or medians.iloc[0] < 1:
            if medians.iloc[0] < 1:
                print(f"Optimized solutions all have null partial bequest in year {my[0]}.", file=description)
            df.drop("partial", axis=1, inplace=True)
            means = df.mean(axis=0, numeric_only=True)
            medians = df.median(axis=0, numeric_only=True)
            my[0] = my[1]

        nfields = len(means)

        df /= 1000
        if len(df) > 0:
            thisyear = year_n[0]
            if log_x:
                print("Histogram: log-scale x-axis, log-spaced bins (zeros excluded).",
                      file=description)

            if objective == "maxBequest":
                fig, axes = plt.subplots()
                if log_x:
                    all_pos = np.concatenate([
                        df[col][(df[col] >= _LOG_FLOOR) & np.isfinite(df[col])].to_numpy()
                        for col in df.columns
                    ])
                    edges = _log_spaced_edges(
                        pd.Series(all_pos), n_positive=len(all_pos)) if len(all_pos) > 0 else None
                else:
                    edges = None
                if edges is not None:
                    sbn.histplot(df, multiple="dodge", kde=True, ax=axes, bins=edges)
                    axes.set_xscale("log")
                    axes.set_xlim(edges[0], edges[-1])
                else:
                    sbn.histplot(df, multiple="dodge", kde=True, ax=axes)
                legend = []
                for q in range(nfields - 1, -1, -1):
                    dmedian = u.d(medians.iloc[q], latex=True)
                    dmean = u.d(means.iloc[q], latex=True)
                    legend.append(f"{my[q]}: $M$: {dmedian}, $\\bar{{x}}$: {dmean}")
                plt.legend(legend, shadow=True)
                plt.xlabel(f"{thisyear} $k")
                plt.title(objective)
                leads = [f"partial {my[0]}", f"  final {my[1]}"]
                leads = leads if nfields == 2 else leads[1:]
            elif nfields == 2:
                fig, axes = plt.subplots(1, 2, figsize=(10, 5))
                cols = ["partial", objective]
                leads = [f"partial {my[0]}", objective]
                for q, col in enumerate(cols):
                    edges = _log_spaced_edges(df[col]) if log_x else None
                    if edges is not None:
                        sbn.histplot(df[col], kde=True, ax=axes[q], bins=edges)
                        axes[q].set_xscale("log")
                        axes[q].set_xlim(edges[0], edges[-1])
                    else:
                        sbn.histplot(df[col], kde=True, ax=axes[q])
                    dmedian = u.d(medians.iloc[q], latex=True)
                    dmean = u.d(means.iloc[q], latex=True)
                    legend = [f"$M$: {dmedian}, $\\bar{{x}}$: {dmean}"]
                    axes[q].set_label(legend)
                    axes[q].legend(labels=legend)
                    axes[q].set_title(leads[q])
                    axes[q].set_xlabel(f"{thisyear} $k")
            else:
                fig, axes = plt.subplots()
                edges = _log_spaced_edges(df[objective]) if log_x else None
                if edges is not None:
                    sbn.histplot(df[objective], kde=True, ax=axes, bins=edges)
                    axes.set_xscale("log")
                    axes.set_xlim(edges[0], edges[-1])
                else:
                    sbn.histplot(df[objective], kde=True, ax=axes)
                dmedian = u.d(medians.iloc[0], latex=True)
                dmean = u.d(means.iloc[0], latex=True)
                legend = [f"$M$: {dmedian}, $\\bar{{x}}$: {dmean}"]
                plt.legend(legend, shadow=True)
                plt.xlabel(f"{thisyear} $k")
                plt.title(objective)
                leads = [objective]

            plt.suptitle(title)

            for q in range(nfields):
                print(f"{leads[q]:>12}: Median ({thisyear} $): {u.d(medians.iloc[q])}", file=description)
                print(f"{leads[q]:>12}:   Mean ({thisyear} $): {u.d(means.iloc[q])}", file=description)
                mmin = 1000 * df.iloc[:, q].min()
                mmax = 1000 * df.iloc[:, q].max()
                print(f"{leads[q]:>12}:           Range: {u.d(mmin)} - {u.d(mmax)}", file=description)

            return fig, description

        return None, description

    def plot_rates_correlations(self, name, tau_kn, N_n, rate_method, rate_frm=None, rate_to=None,
                                tag="", share_range=False):
        """Plot correlations between various rates."""
        rate_names = [
            "S&P500 (incl. div.)",
            "Baa Corp. Bonds",
            "10-y T-Notes",
            "Inflation",
        ]

        df = pd.DataFrame()
        for k, name in enumerate(rate_names):
            data = 100 * tau_kn[k]
            df[name] = data

        g = sbn.PairGrid(df, diag_sharey=False, height=1.8, aspect=1)
        if share_range:
            minval = df.min().min() - 5
            maxval = df.max().max() + 5
            g.set(xlim=(minval, maxval), ylim=(minval, maxval))
        g.map_upper(sbn.scatterplot)
        g.map_lower(sbn.kdeplot)
        g.map_diag(sbn.histplot, color="orange")

        # Put zero axes on off-diagonal plots.
        imod = len(rate_names) + 1
        for i, ax in enumerate(g.axes.flat):
            ax.axvline(x=0, color="grey", linewidth=1, linestyle=":")
            if i % imod != 0:
                ax.axhline(y=0, color="grey", linewidth=1, linestyle=":")

        title = name + "\n"
        title += f"Rates Correlations (N={N_n}) {rate_method}"
        if rate_method in ("historical", "histochastic"):
            title += f" ({rate_frm}-{rate_to})"

        if tag != "":
            title += " - " + tag

        g.figure.suptitle(title, y=1.08)
        return g.figure

    def plot_rates(self, name, tau_kn, year_n, N_k,
                   rate_method, rate_frm=None, rate_to=None, tag=""):
        """Plot rate values used over the time horizon."""
        fig, ax = plt.subplots()
        title = name + "\nReturn & Inflation Rates (" + str(rate_method)
        if rate_method in HISTORICAL_RANGE_METHODS:
            title += f" {rate_frm}-{rate_to}"
        title += ")"

        if tag != "":
            title += " - " + tag

        rate_name = [
            "S&P500 (incl. div.)",
            "Baa Corp. Bonds",
            "10-y T-Notes",
            "Inflation",
        ]
        ltype = ["-", "-.", ":", "--"]

        for k in range(N_k):
            data = 100 * tau_kn[k]
            # Use ddof=1 to match pandas' statistical calculations from numpy.
            label = (
                rate_name[k] + " <" + "{:.1f}".format(np.mean(data)) + " +/- {:.1f}".format(np.std(data, ddof=1)) + "%>"
            )
            ax.plot(year_n, data, label=label, ls=ltype[k % N_k])

        ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
        ax.legend(loc="best", reverse=False, fontsize=8, framealpha=0.7)
        ax.set_title(title)
        ax.set_xlabel("year")
        ax.set_ylabel("%")

        return fig

    def plot_rates_distributions(self, frm, to, SP500, BondsBaa, TNotes, Inflation, FROM):
        """Plot histograms of the rates distributions."""
        title = f"Rates from {frm} to {to}"
        # Bring year values to indices.
        frm -= FROM
        to -= FROM

        nbins = int((to - frm) / 4)
        fig, ax = plt.subplots(1, 4, sharey=True, sharex=True, tight_layout=True)

        dat0 = np.array(SP500[frm:to])
        dat1 = np.array(BondsBaa[frm:to])
        dat2 = np.array(TNotes[frm:to])
        dat3 = np.array(Inflation[frm:to])

        fig.suptitle(title)
        ax[0].set_title("S&P500")
        label = "<>: " + u.pc(np.mean(dat0), 2, 1)
        ax[0].hist(dat0, bins=nbins, label=label)
        ax[0].legend(loc="upper left", fontsize=8, framealpha=0.7)

        ax[1].set_title("BondsBaa")
        label = "<>: " + u.pc(np.mean(dat1), 2, 1)
        ax[1].hist(dat1, bins=nbins, label=label)
        ax[1].legend(loc="upper left", fontsize=8, framealpha=0.7)

        ax[2].set_title("TNotes")
        label = "<>: " + u.pc(np.mean(dat2), 2, 1)
        ax[2].hist(dat2, bins=nbins, label=label)
        ax[2].legend(loc="upper left", fontsize=8, framealpha=0.7)

        ax[3].set_title("Inflation")
        label = "<>: " + u.pc(np.mean(dat3), 2, 1)
        ax[3].hist(dat3, bins=nbins, label=label)
        ax[3].legend(loc="upper left", fontsize=8, framealpha=0.7)

        return fig

    def plot_gross_income(self, year_n, G_n, gamma_n, value, title, tax_brackets):
        """Plot gross income over time."""
        style = {"taxable income": "-"}
        if value == "nominal":
            series = {"taxable income": G_n}
            yformat = r"\$k (nominal)"
            infladjust = gamma_n[:-1]
        else:
            series = {"taxable income": G_n / gamma_n[:-1]}
            yformat = r"\$k (" + str(year_n[0]) + r"\$)"
            infladjust = 1
        fig, ax = self._line_income_plot(year_n, series, style, title, yformat)
        # Overlay tax brackets
        for key in tax_brackets:
            data_adj = tax_brackets[key] * infladjust
            ax.plot(year_n, data_adj, label=key, ls=":")
        ax.grid(visible=True, which='both')
        ax.legend(loc="upper left", reverse=True, fontsize=8, framealpha=0.3)

        return fig

    def plot_profile(self, year_n, xi_n, title, inames):
        """Plot profile over time."""
        style = {"profile": "-"}
        series = {"profile": xi_n}

        return self._line_income_plot(year_n, series, style, title, yformat=r"$\xi$")[0]

    def plot_net_spending(self, year_n, g_n, xi_n, xiBar_n, gamma_n, value, title, inames):
        """Plot net spending over time."""
        style = {"net": "-", "target": ":"}
        if value == "nominal":
            series = {"net": g_n, "target": (g_n[0] / xi_n[0]) * xiBar_n}
            yformat = r"\$k (nominal)"
        else:
            series = {"net": g_n / gamma_n[:-1], "target": (g_n[0] / xi_n[0]) * xi_n}
            yformat = r"\$k (" + str(year_n[0]) + r"\$)"

        return self._line_income_plot(year_n, series, style, title, yformat)[0]

    def plot_asset_composition(self, year_n, inames, b_ijkn, gamma_n, value, name, tag):
        """Plot asset composition over time."""
        if value == "nominal":
            yformat = r"\$k (nominal)"
            infladjust = 1
        else:
            yformat = r"\$k (" + str(year_n[0]) + r"\$)"
            infladjust = gamma_n
        years_n = np.array(year_n)
        years_n = np.append(years_n, [years_n[-1] + 1])
        y2stack = {}
        jDic = {"taxable": 0, "tax-deferred": 1, "tax-free": 2}
        kDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}
        figures = []
        for jkey in jDic:
            stackNames = []
            for kkey in kDic:
                namek = kkey + " / " + jkey
                stackNames.append(namek)
                y2stack[namek] = np.zeros((len(inames), len(years_n)))
                for i in range(len(inames)):
                    y2stack[namek][i][:] = b_ijkn[i][jDic[jkey]][kDic[kkey]][:] / infladjust
            title = name + "\nAsset Composition - " + jkey
            if tag:
                title += " - " + tag
            fig, ax = self._stack_plot(years_n, inames, title, range(len(inames)),
                                       y2stack, stackNames, "upper left", yformat)
            figures.append(fig)

        return figures

    def plot_allocations(self, year_n, inames, alpha_ijkn, ARCoord, title):
        """Plot allocations over time."""
        count = len(inames)
        if ARCoord == "spouses":
            acList = [ARCoord]
            count = 1
        elif ARCoord == "individual":
            acList = [ARCoord]
        elif ARCoord == "account":
            acList = ["taxable", "tax-deferred", "tax-free"]
        else:
            raise ValueError(f"Unknown coordination {ARCoord}.")
        figures = []
        assetDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}
        blank = ["", ""]
        for i in range(count):
            y2stack = {}
            for acType in acList:
                stackNames = []
                for key in assetDic:
                    # aname = key + " / " + acType
                    aname = key
                    stackNames.append(aname)
                    y2stack[aname] = np.zeros((count, len(year_n)))
                    y2stack[aname][i][:] = alpha_ijkn[i, acList.index(acType), assetDic[key], : len(year_n)]
                t = title + f" - {acType} {inames[i]}"
                fig, ax = self._stack_plot(year_n, blank, t, [i], y2stack, stackNames, "upper left", "percent")
                figures.append(fig)

        return figures

    def plot_accounts(self, year_n, savings_in, gamma_n, value, title, inames):
        """Plot accounts over time."""
        stypes = list(savings_in.keys())
        year_n_full = np.append(year_n, [year_n[-1] + 1])
        if value == "nominal":
            yformat = r"\$k (nominal)"
            savings = savings_in
        else:
            yformat = r"\$k (" + str(year_n[0]) + r"\$)"
            savings = {k: v / gamma_n for k, v in savings_in.items()}
        fig, ax = self._stack_plot(year_n_full, inames, title, range(len(inames)),
                                   savings, stypes, "upper left", yformat)

        return fig

    def plot_sources(self, year_n, sources_in, gamma_n, value, title, inames):
        """Plot sources over time."""
        stypes = list(sources_in.keys())
        if value == "nominal":
            yformat = r"\$k (nominal)"
            sources = sources_in
        else:
            yformat = r"\$k (" + str(year_n[0]) + r"\$)"
            sources = {k: v / gamma_n[:-1] for k, v in sources_in.items()}
        fig, ax = self._stack_plot(year_n, inames, title, range(len(inames)), sources, stypes, "upper left", yformat)

        return fig

    def plot_taxes(self, year_n, T_n, M_n, gamma_n, value, title, inames):
        """Plot taxes over time."""
        style = {"income tax": "-", "Medicare": "-."}
        if value == "nominal":
            series = {"income tax": T_n, "Medicare": M_n}
            yformat = r"\$k (nominal)"
        else:
            series = {"income tax": T_n / gamma_n[:-1], "Medicare": M_n / gamma_n[:-1]}
            yformat = r"\$k (" + str(year_n[0]) + r"\$)"
        fig, ax = self._line_income_plot(year_n, series, style, title, yformat)

        return fig
