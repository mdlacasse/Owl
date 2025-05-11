"""

Owl/plots
---------

A retirement planner using linear programming optimization.

This module contains all plotting functions used by the Owl project.

Copyright (C) 2025 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as tk
import io
import os

from owlplanner import utils as u

os.environ["JUPYTER_PLATFORM_DIRS"] = "1"
import seaborn as sbn   # noqa: E402


# Set the style for all plots.
def set_plot_style():
    """
    Set the style for all matplotlib plots.
    """
    plt.rcParams.update({'figure.autolayout': True})
    plt.rcParams.update({'figure.figsize': (6, 4)})
    plt.rcParams.update({'axes.grid': True})
    plt.rcParams.update({'axes.grid.which': 'both'})


set_plot_style()


def line_income_plot(x, series, style, title, yformat="\\$k"):
    """
    Core line plotter function.
    """
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


def stack_plot(x, inames, title, irange, series, snames, location, yformat="\\$k"):
    """
    Core function for stacked plots.
    """
    nonzeroSeries = {}
    for sname in snames:
        for i in irange:
            tmp = series[sname][i]
            if sum(tmp) > 1.0:
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


def show_histogram_results(objective, df, N, year_n, n_d=None, N_i=1, phi_j=None):
    """
    Show a histogram of values from historical data or Monte Carlo simulations.
    """
    description = io.StringIO()

    pSuccess = u.pc(len(df) / N)
    print(f"Success rate: {pSuccess} on {N} samples.", file=description)
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

    df /= 1000
    if len(df) > 0:
        thisyear = year_n[0]
        if objective == "maxBequest":
            fig, axes = plt.subplots()
            # Show both partial and final bequests in the same histogram.
            sbn.histplot(df, multiple="dodge", kde=True, ax=axes)
            legend = []
            # Don't know why but legend is reversed from df.
            for q in range(len(means) - 1, -1, -1):
                dmedian = u.d(medians.iloc[q], latex=True)
                dmean = u.d(means.iloc[q], latex=True)
                legend.append(f"{my[q]}: $M$: {dmedian}, $\\bar{{x}}$: {dmean}")
            plt.legend(legend, shadow=True)
            plt.xlabel(f"{thisyear} $k")
            plt.title(objective)
            leads = [f"partial {my[0]}", f"  final {my[1]}"]
        elif len(means) == 2:
            # Show partial bequest and net spending as two separate histograms.
            fig, axes = plt.subplots(1, 2, figsize=(10, 5))
            cols = ["partial", objective]
            leads = [f"partial {my[0]}", objective]
            for q in range(2):
                sbn.histplot(df[cols[q]], kde=True, ax=axes[q])
                dmedian = u.d(medians.iloc[q], latex=True)
                dmean = u.d(means.iloc[q], latex=True)
                legend = [f"$M$: {dmedian}, $\\bar{{x}}$: {dmean}"]
                axes[q].set_label(legend)
                axes[q].legend(labels=legend)
                axes[q].set_title(leads[q])
                axes[q].set_xlabel(f"{thisyear} $k")
        else:
            # Show net spending as single histogram.
            fig, axes = plt.subplots()
            sbn.histplot(df[objective], kde=True, ax=axes)
            dmedian = u.d(medians.iloc[0], latex=True)
            dmean = u.d(means.iloc[0], latex=True)
            legend = [f"$M$: {dmedian}, $\\bar{{x}}$: {dmean}"]
            plt.legend(legend, shadow=True)
            plt.xlabel(f"{thisyear} $k")
            plt.title(objective)
            leads = [objective]

        plt.suptitle(title)

        for q in range(len(means)):
            print(f"{leads[q]:>12}: Median ({thisyear} $): {u.d(medians.iloc[q])}", file=description)
            print(f"{leads[q]:>12}:   Mean ({thisyear} $): {u.d(means.iloc[q])}", file=description)
            mmin = 1000 * df.iloc[:, q].min()
            mmax = 1000 * df.iloc[:, q].max()
            print(f"{leads[q]:>12}:           Range: {u.d(mmin)} - {u.d(mmax)}", file=description)
            nzeros = len(df.iloc[:, q][df.iloc[:, q] < 0.001])
            print(f"{leads[q]:>12}:    N zero solns: {nzeros}", file=description)

        return fig, description

    return None, description


def show_rates_correlations(name, tau_kn, N_n, rate_method, rate_frm=None, rate_to=None,
                            tag="", share_range=False):
    """
    Plot correlations between various rates.
    """

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
    if rate_method in ["historical", "histochastic"]:
        title += f" ({rate_frm}-{rate_to})"

    if tag != "":
        title += " - " + tag

    g.figure.suptitle(title, y=1.08)
    return g.figure


def show_rates(name, tau_kn, year_n, year_frac_left, N_k, rate_method, rate_frm=None, rate_to=None, tag=""):
    """
    Plot rate values used over the time horizon.
    """
    fig, ax = plt.subplots()
    title = name + "\nReturn & Inflation Rates (" + str(rate_method)
    if rate_method in ["historical", "histochastic", "historical average"]:
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
        # Don't plot partial rates for current year if mid-year.
        if year_frac_left == 1:
            data = 100 * tau_kn[k]
            years = year_n
        else:
            data = 100 * tau_kn[k, 1:]
            years = year_n[1:]

        # Use ddof=1 to match pandas' statistical calculations from numpy.
        label = (
            rate_name[k] + " <" + "{:.1f}".format(np.mean(data)) + " +/- {:.1f}".format(np.std(data, ddof=1)) + "%>"
        )
        ax.plot(years, data, label=label, ls=ltype[k % N_k])

    ax.xaxis.set_major_locator(tk.MaxNLocator(integer=True))
    ax.legend(loc="best", reverse=False, fontsize=8, framealpha=0.7)
    ax.set_title(title)
    ax.set_xlabel("year")
    ax.set_ylabel("%")

    return fig


def show_rates_distributions(frm, to, SP500, BondsBaa, TNotes, Inflation, FROM):
    """
    Plot histograms of the rates distributions.
    """
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


def plot_gross_income(year_n, G_n, gamma_n, value, title, tax_brackets):
    style = {"taxable income": "-"}
    if value == "nominal":
        series = {"taxable income": G_n}
        yformat = "\\$k (nominal)"
        infladjust = gamma_n[:-1]
    else:
        series = {"taxable income": G_n / gamma_n[:-1]}
        yformat = "\\$k (" + str(year_n[0]) + "\\$)"
        infladjust = 1
    fig, ax = line_income_plot(year_n, series, style, title, yformat)
    # Overlay tax brackets
    for key in tax_brackets:
        data_adj = tax_brackets[key] * infladjust
        ax.plot(year_n, data_adj, label=key, ls=":")
    ax.grid(visible=True, which='both')
    ax.legend(loc="upper left", reverse=True, fontsize=8, framealpha=0.3)

    return fig


def plot_profile(year_n, xi_n, title, inames):
    style = {"profile": "-"}
    series = {"profile": xi_n}

    return line_income_plot(year_n, series, style, title, yformat="$\\xi$")[0]


def plot_net_spending(year_n, g_n, xi_n, xiBar_n, gamma_n, value, title, inames):
    style = {"net": "-", "target": ":"}
    if value == "nominal":
        series = {"net": g_n, "target": (g_n[0] / xi_n[0]) * xiBar_n}
        yformat = "\\$k (nominal)"
    else:
        series = {"net": g_n / gamma_n[:-1], "target": (g_n[0] / xi_n[0]) * xi_n}
        yformat = "\\$k (" + str(year_n[0]) + "\\$)"

    return line_income_plot(year_n, series, style, title, yformat)[0]


def plot_asset_distribution(year_n, inames, b_ijkn, gamma_n, value, name, tag):
    if value == "nominal":
        yformat = "\\$k (nominal)"
        infladjust = 1
    else:
        yformat = "\\$k (" + str(year_n[0]) + "\\$)"
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
        title = name + "\nAssets Distribution - " + jkey
        if tag:
            title += " - " + tag
        fig, ax = stack_plot(years_n, inames, title, range(len(inames)), y2stack, stackNames, "upper left", yformat)
        figures.append(fig)

    return figures


def plot_allocations(year_n, inames, alpha_ijkn, ARCoord, title):
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
    for i in range(count):
        y2stack = {}
        for acType in acList:
            stackNames = []
            for key in assetDic:
                aname = key + " / " + acType
                stackNames.append(aname)
                y2stack[aname] = np.zeros((count, len(year_n)))
                y2stack[aname][i][:] = alpha_ijkn[i, acList.index(acType), assetDic[key], : len(year_n)]
            t = title + f" - {acType}"
            fig, ax = stack_plot(year_n, inames, t, [i], y2stack, stackNames, "upper left", "percent")
            figures.append(fig)

    return figures


def plot_accounts(year_n, savings_in, gamma_n, value, title, inames):
    stypes = list(savings_in.keys())
    year_n_full = np.append(year_n, [year_n[-1] + 1])
    if value == "nominal":
        yformat = "\\$k (nominal)"
        savings = savings_in
    else:
        yformat = "\\$k (" + str(year_n[0]) + "\\$)"
        savings = {k: v / gamma_n for k, v in savings_in.items()}
    fig, ax = stack_plot(year_n_full, inames, title, range(len(inames)), savings, stypes, "upper left", yformat)

    return fig


def plot_sources(year_n, sources_in, gamma_n, value, title, inames):
    stypes = list(sources_in.keys())
    if value == "nominal":
        yformat = "\\$k (nominal)"
        sources = sources_in
    else:
        yformat = "\\$k (" + str(year_n[0]) + "\\$)"
        sources = {k: v / gamma_n[:-1] for k, v in sources_in.items()}
    fig, ax = stack_plot(year_n, inames, title, range(len(inames)), sources, stypes, "upper left", yformat)

    return fig


def plot_taxes(year_n, T_n, M_n, gamma_n, value, title, inames):
    style = {"income taxes": "-", "Medicare": "-."}
    if value == "nominal":
        series = {"income taxes": T_n, "Medicare": M_n}
        yformat = "\\$k (nominal)"
    else:
        series = {"income taxes": T_n / gamma_n[:-1], "Medicare": M_n / gamma_n[:-1]}
        yformat = "\\$k (" + str(year_n[0]) + "\\$)"
    fig, ax = line_income_plot(year_n, series, style, title, yformat)

    return fig
