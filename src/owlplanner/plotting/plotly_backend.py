"""
Plotly backend implementation for plotting retirement planning results.

This module provides the Plotly-based implementation of the plot backend
interface for creating interactive visualizations of retirement planning data.

Copyright (C) 2025-2026 The Owl Authors

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
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# import plotly.io as pio

import io
from scipy import stats

from .base import PlotBackend
from .. import utils as u
from ..rate_models.constants import (
    HISTORICAL_RANGE_METHODS,
    RATE_DISPLAY_NAMES,
    RATE_DISPLAY_NAMES_SHORT,
)

# Canonical color maps — shared by cashflow_mix and lifetime_allocation so that
# the same category always gets the same color in both chart types.
_INCOME_COLORS = {
    "portfolio":   "#795548",
    "ss":          "#2196F3",
    "pension":     "#009688",
    "wages":       "#FF9800",
    "spia":        "#E91E63",
    "fixedassets": "#8BC34A",
    "other":       "#673AB7",
    "bti":         "#CDDC39",
}
_OUTFLOW_COLORS = {
    "living":     "#2196F3",
    "taxes":      "#F44336",
    "state_taxes": "#C62828",
    "healthcare": "#FF9800",
    "debt":       "#9E9E9E",
    "bti":        "#FF6F00",
    "bequest":    "#4CAF50",
    "heirtax":    "#E91E63",
}

# Reusable legend layouts for plotly
_LEGEND_TOP = dict(
    traceorder="reversed",
    yanchor="top",
    y=0.99,
    xanchor="left",
    x=0.01,
    bgcolor="rgba(255, 255, 255, 0.5)",
)
_LEGEND_BOTTOM = dict(
    yanchor="bottom",
    y=-0.5,
    xanchor="center",
    x=0.5,
    bgcolor="rgba(0, 0, 0, 0)",
    orientation="h",
)
_LEGEND_BOTTOM_REVERSED = {**_LEGEND_BOTTOM, "traceorder": "reversed"}


class PlotlyBackend(PlotBackend):
    """Plotly implementation of plot backend."""

    def __init__(self):
        """Initialize the plotly backend."""
        # Set default template and layout
        self.template = "plotly_white"
        self.layout = dict(
            showlegend=True,
            legend=_LEGEND_TOP,
            xaxis=dict(
                showgrid=True,
                griddash="dot",
                gridcolor="lightgray",
                zeroline=True,
                zerolinecolor="gray",
                zerolinewidth=1,
            ),
            yaxis=dict(
                showgrid=True,
                griddash="dot",
                gridcolor="lightgray",
                zeroline=True,
                zerolinecolor="gray",
                zerolinewidth=1,
            ),
        )
        # Setting to "browser" will open each graph in a separate tab.
        # pio.renderers.default = "browser"

    def jupyter_renderer(self, fig):
        """Simple renderer for plotly in Jupyter notebook."""
        return fig.show()

    def plot_profile(self, year_n, xi_n, title, inames):
        """Plot profile over time."""
        fig = go.Figure()

        # Add profile line
        fig.add_trace(go.Scatter(
            x=year_n,
            y=xi_n,
            name="profile",
            line=dict(width=2)
        ))

        title = title.replace("\n", "<br>")
        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title="ξ",
            template=self.template,
            showlegend=True,
            legend=_LEGEND_BOTTOM_REVERSED,
            margin=dict(b=150),
        )

        # Format y-axis as number
        fig.update_yaxes(tickformat=",.1f")

        return fig

    def plot_gross_income(self, year_n, G_n, gamma_n, value, title, tax_brackets):
        """Plot gross income over time."""
        fig = go.Figure()

        # Add taxable income line
        if value == "nominal":
            y_data = G_n / 1000
            y_title = "$k (nominal)"
            infladjust = gamma_n[:-1]
        else:
            y_data = G_n / gamma_n[:-1] / 1000
            y_title = f"$k ({year_n[0]}$)"
            infladjust = 1

        fig.add_trace(go.Scatter(
            x=year_n,
            y=y_data,
            name="taxable income",
            line=dict(width=2)
        ))

        # Add tax brackets
        for key, bracket_data in tax_brackets.items():
            data_adj = bracket_data * infladjust / 1000
            fig.add_trace(go.Scatter(
                x=year_n,
                y=data_adj,
                name=key,
                line=dict(width=1, dash="dot")
            ))

        title = title.replace("\n", "<br>")
        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title=y_title,
            template=self.template,
            showlegend=True,
            legend=_LEGEND_BOTTOM,
            margin=dict(b=150),
        )

        # Format y-axis as number
        fig.update_yaxes(tickformat=",.0f")

        return fig

    def plot_net_spending(self, year_n, g_n, xi_n, xiBar_n, gamma_n, value, title, inames):
        """Plot net spending over time."""
        fig = go.Figure()

        # Calculate data based on value type
        if value == "nominal":
            net_data = g_n / 1000
            target_data = (g_n[0] / xi_n[0]) * xiBar_n / 1000
            y_title = "$k (nominal)"
        else:
            net_data = g_n / gamma_n[:-1] / 1000
            target_data = (g_n[0] / xi_n[0]) * xi_n / 1000
            y_title = f"$k ({year_n[0]}$)"

        # Add net spending line
        fig.add_trace(go.Scatter(
            x=year_n,
            y=net_data,
            name="net",
            line=dict(width=2)
        ))

        # Add target line
        fig.add_trace(go.Scatter(
            x=year_n,
            y=target_data,
            name="target",
            line=dict(width=1, dash="dot")
        ))

        title = title.replace("\n", "<br>")
        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title=y_title,
            template=self.template,
            showlegend=True,
            legend={**_LEGEND_BOTTOM, "y": -0.4},
            margin=dict(b=150)
        )

        # Format y-axis as k
        fig.update_yaxes(tickformat=",.0f")

        ymin = np.min(net_data)
        ymax = np.max(net_data)
        if np.abs(ymax - ymin) < 1:
            fig.update_layout(yaxis=dict(range=[np.floor(ymin)-1, np.ceil(ymax)+1]))

        return fig

    def plot_taxes(self, year_n, T_n, M_n, gamma_n, value, title, inames, A_n=None, ST_n=None):
        """Plot taxes over time. A_n: optional ACA costs. ST_n: optional state income tax."""
        fig = go.Figure()

        # Calculate data based on value type
        if value == "nominal":
            income_tax_data = T_n / 1000
            medicare_data = M_n / 1000
            aca_data = A_n / 1000 if A_n is not None else None
            st_data = ST_n / 1000 if ST_n is not None else None
            y_title = "$k (nominal)"
        else:
            income_tax_data = T_n / gamma_n[:-1] / 1000
            medicare_data = M_n / gamma_n[:-1] / 1000
            aca_data = A_n / gamma_n[:-1] / 1000 if A_n is not None else None
            st_data = ST_n / gamma_n[:-1] / 1000 if ST_n is not None else None
            y_title = f"$k ({year_n[0]}$)"

        # Add income taxes line
        fig.add_trace(go.Scatter(
            x=year_n,
            y=income_tax_data,
            name="income tax",
            line=dict(width=2)
        ))

        # Add Medicare line
        fig.add_trace(go.Scatter(
            x=year_n,
            y=medicare_data,
            name="Medicare",
            line=dict(width=2, dash="dot")
        ))

        # Add ACA line when configured
        if aca_data is not None and (aca_data > 0).any():
            fig.add_trace(go.Scatter(
                x=year_n,
                y=aca_data,
                name="ACA",
                line=dict(width=2, dash="dash")
            ))

        # Add state income tax line when configured
        if st_data is not None and (st_data > 0).any():
            fig.add_trace(go.Scatter(
                x=year_n,
                y=st_data,
                name="state tax",
                line=dict(width=2, dash="longdash")
            ))

        title = title.replace("\n", "<br>")
        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title=y_title,
            template=self.template,
            showlegend=True,
            legend={**_LEGEND_BOTTOM, "y": -0.4},
            margin=dict(b=150),
        )

        # Format y-axis as currency
        fig.update_yaxes(tickformat=",.0f")

        return fig

    def plot_rates(self, name, tau_kn, year_n, N_k, rate_method, rate_frm=None, rate_to=None, tag=""):
        """Plot rate values used over the time horizon."""
        fig = go.Figure()

        # Build title
        title = name + "<br>Return & Inflation Rates (" + str(rate_method)
        if rate_method in HISTORICAL_RANGE_METHODS:
            title += f" {rate_frm}-{rate_to}"
        title += ")"
        if tag:
            title += " - " + tag

        # Define rate names and line styles
        rate_names = list(RATE_DISPLAY_NAMES)
        line_styles = ["solid", "dot", "dash", "longdash"]

        # Plot each rate
        for k in range(N_k):
            data = 100 * tau_kn[k]

            # Calculate mean and std
            mean_val = np.mean(data)
            std_val = np.std(data, ddof=1)  # Use ddof=1 to match pandas
            label = f"{rate_names[k]} <{mean_val:.1f} +/- {std_val:.1f}%>"

            # Add trace
            fig.add_trace(go.Scatter(
                x=year_n,
                y=data,
                name=label,
                line=dict(
                    width=2,
                    dash=line_styles[k % N_k]
                )
            ))

        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title="%",
            template=self.template,
            showlegend=True,
            legend={**_LEGEND_BOTTOM, "y": -0.60},
            margin=dict(b=150),
        )

        # Format y-axis as percentage
        fig.update_yaxes(tickformat=".1f")

        return fig

    def plot_rates_distributions(self, frm, to, SP500, BondsBaa, TNotes, Inflation, FROM):
        """Plot histograms of the rates distributions. Annotated mean is geometric (compound) mean."""
        # Create subplot figure
        fig = make_subplots(
            rows=1, cols=4,
            subplot_titles=RATE_DISPLAY_NAMES_SHORT,
            shared_yaxes=True
        )

        # Calculate number of bins
        nbins = int((to - frm) / 4)

        # Convert year values to indices
        frm_idx = frm - FROM
        to_idx = to - FROM

        # Get data arrays
        data = [
            np.array(SP500[frm_idx:to_idx]),
            np.array(BondsBaa[frm_idx:to_idx]),
            np.array(TNotes[frm_idx:to_idx]),
            np.array(Inflation[frm_idx:to_idx])
        ]

        # Add histograms
        for i, dat in enumerate(data):
            mean_val = u.geometric_mean_pct(dat)
            label = f"<>: {u.pc(mean_val, 2, 1)}"

            fig.add_trace(
                go.Histogram(
                    x=dat,
                    nbinsx=nbins,
                    name=label,
                    showlegend=False,
                    marker_color="orange"
                ),
                row=1, col=i+1
            )

            # Add mean annotation
            fig.add_annotation(
                x=0.5, y=0.95,
                xref=f"x{i+1}",
                yref="paper",
                text=label,
                showarrow=False,
                font=dict(size=10),
                bgcolor="rgba(255, 255, 255, 0.7)"
            )

        # Update layout
        fig.update_layout(
            title=f"Rates from {frm} to {to}",
            template=self.template,
            showlegend=False,
            height=400,
            width=1200
        )

        # Update axes
        for i in range(4):
            fig.update_xaxes(
                title_text="%",
                showgrid=True,
                gridcolor="lightgray",
                zeroline=True,
                zerolinecolor="gray",
                zerolinewidth=1,
                row=1, col=i+1
            )
            fig.update_yaxes(
                showgrid=True,
                gridcolor="lightgray",
                zeroline=True,
                zerolinecolor="gray",
                zerolinewidth=1,
                row=1, col=i+1
            )

        return fig

    def plot_rates_cdf(self, name, tau_kn, rate_method, SP500, BondsBaa, TNotes, Inflation, FROM,
                       rate_frm=None, rate_to=None, tag=""):
        """Plot empirical CDFs of rates, with historical range overlay for historical methods."""
        show_hist = (rate_method in HISTORICAL_RANGE_METHODS and rate_frm is not None and rate_to is not None)
        hist_sources = [SP500, BondsBaa, TNotes, Inflation]
        N_samples = tau_kn.shape[1]

        fig = make_subplots(rows=1, cols=4, subplot_titles=list(RATE_DISPLAY_NAMES_SHORT), shared_yaxes=True)

        colors = ["#4C78A8", "#F58518", "#54A24B", "#E45756"]

        for k, rate_name in enumerate(RATE_DISPLAY_NAMES_SHORT):
            mc_data = np.sort(100.0 * tau_kn[k])
            n_mc = len(mc_data)
            p_mc = np.arange(1, n_mc + 1) / n_mc

            fig.add_trace(go.Scatter(
                x=mc_data, y=p_mc, mode="lines",
                name=f"{rate_name}: {rate_method} (N={N_samples})",
                line=dict(color=colors[k], width=2, shape="hv"),
                showlegend=True,
                legendgroup=f"mc_{k}",
            ), row=1, col=k + 1)

            if show_hist:
                h_arr = np.sort(np.array(hist_sources[k][rate_frm - FROM: rate_to - FROM], dtype=float))
                n_h = len(h_arr)
                p_h = np.arange(1, n_h + 1) / n_h
                fig.add_trace(go.Scatter(
                    x=h_arr, y=p_h, mode="lines",
                    name=f"{rate_name}: Historical {rate_frm}-{rate_to} (N={n_h})",
                    line=dict(color="gray", width=2, dash="dash", shape="hv"),
                    showlegend=True,
                    legendgroup=f"hist_{k}",
                ), row=1, col=k + 1)

            fig.add_shape(
                type="line",
                x0=0, x1=0, y0=0, y1=1,
                xref=f"x{k + 1}", yref="paper",
                line=dict(color="lightgray", width=1, dash="dot"),
            )

        title = name + "<br>Rates CDF - " + str(rate_method)
        if rate_method in HISTORICAL_RANGE_METHODS:
            title += f" ({rate_frm}-{rate_to})"
        if tag:
            title += " - " + tag

        fig.update_layout(
            title=title,
            template=self.template,
            showlegend=True,
            legend={"y": -0.30, "orientation": "h"},
            margin=dict(b=150),
            height=450,
        )
        fig.update_yaxes(range=[0, 1], tickformat=".0%", title_text="Cumulative Probability", col=1)
        fig.update_xaxes(title_text="%")

        return fig

    def plot_rates_correlations(self, pname, tau_kn, rate_method, rate_frm=None, rate_to=None,
                                tag="", share_range=False):
        """Plot correlations between various rates."""
        # Create DataFrame with rate data
        rate_names = RATE_DISPLAY_NAMES
        df = pd.DataFrame()
        for k, name in enumerate(rate_names):
            df[name] = 100 * tau_kn[k]  # Convert to percentage

        # Create subplot figure
        n_vars = len(rate_names)
        fig = make_subplots(
            rows=n_vars, cols=n_vars,
            # subplot_titles=rate_names,  # Only use rate names for first row
            shared_xaxes=True,  # Share x-axes
            vertical_spacing=0.05,
            horizontal_spacing=0.05
        )

        # Set range if requested
        if share_range:
            minval = df.min().min() - 5
            maxval = df.max().max() + 5
        else:
            minval = maxval = None

        # Add plots
        for i in range(n_vars):
            for j in range(n_vars):
                if i == j:
                    # Diagonal: histogram
                    fig.add_trace(
                        go.Histogram(
                            x=df[rate_names[i]],
                            marker_color="orange",
                            showlegend=False
                        ),
                        row=i+1, col=j+1
                    )
                    # Set y-axis for histogram to be independent and start from 0
                    fig.update_yaxes(
                        showticklabels=True,
                        row=i+1,
                        col=j+1,
                        range=[0, None],  # Start from 0, let max be automatic
                        autorange=True,  # Allow automatic scaling
                        matches=None,  # Don't share with other plots
                        scaleanchor=None,  # Don't link to any other axis
                        constrain=None  # Don't constrain the range
                    )
                elif i < j:
                    # Upper triangle: scatter plot
                    fig.add_trace(
                        go.Scatter(
                            x=df[rate_names[j]],
                            y=df[rate_names[i]],
                            mode="markers",
                            marker=dict(
                                size=6,
                                opacity=0.5
                            ),
                            showlegend=False
                        ),
                        row=i+1, col=j+1
                    )
                    # Set range for scatter plot if requested
                    if share_range and minval is not None and maxval is not None:
                        fig.update_yaxes(range=[minval, maxval], row=i+1, col=j+1)
                else:
                    # Lower triangle: KDE
                    x = df[rate_names[j]]
                    y = df[rate_names[i]]
                    kde = stats.gaussian_kde(np.vstack([x, y]))
                    x_grid = np.linspace(x.min(), x.max(), 50)
                    y_grid = np.linspace(y.min(), y.max(), 50)
                    X, Y = np.meshgrid(x_grid, y_grid)
                    Z = kde(np.vstack([X.ravel(), Y.ravel()])).reshape(X.shape)

                    fig.add_trace(
                        go.Contour(
                            x=x_grid,
                            y=y_grid,
                            z=Z,
                            showscale=False,
                            colorscale="Viridis",
                            showlegend=False
                        ),
                        row=i+1, col=j+1
                    )
                    # Set range for KDE plot if requested
                    if share_range and minval is not None and maxval is not None:
                        fig.update_yaxes(range=[minval, maxval], row=i+1, col=j+1)

        # Update layout
        N_samples = tau_kn.shape[1]
        title = pname + "<br>"
        title += f"Rates Correlations (N={N_samples}) {rate_method}"
        if rate_method in HISTORICAL_RANGE_METHODS:
            title += f" ({rate_frm}-{rate_to})"
        if tag:
            title += " - " + tag

        fig.update_layout(
            title=title,
            template=self.template,
            height=800,
            width=800,
            showlegend=False
        )

        # Update axes
        for i in range(n_vars):
            for j in range(n_vars):
                # Add zero lines
                fig.add_shape(
                    type="line",
                    x0=0, y0=0, x1=0, y1=1,
                    xref=f"x{j+1}", yref=f"y{i+1}",
                    line=dict(color="gray", width=1, dash="dot")
                )
                if i != j:
                    fig.add_shape(
                        type="line",
                        x0=0, y0=0, x1=1, y1=0,
                        xref=f"x{j+1}", yref=f"y{i+1}",
                        line=dict(color="gray", width=1, dash="dot")
                    )

                # Update axis labels
                if i == n_vars-1:  # Bottom row
                    fig.update_xaxes(title_text=rate_names[j], row=i+1, col=j+1)
                if j == 0:  # Left column
                    fig.update_yaxes(title_text=rate_names[i], row=i+1, col=j+1)

        return fig

    def plot_histogram_results(self, objective, df, N, year_n, n_d=None, N_i=1, phi_j=None, log_x=False):  # noqa: C901
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

        def _log_spaced_edges(series, n_positive=None, floor=_LOG_FLOOR):
            """Log-spaced bin edges from positive values >= floor. Returns (edges, positive_mask).
            n_positive: if given, used for adaptive bin count; else derived from series."""
            pos = series.to_numpy(dtype=float)
            pos = pos[(pos >= floor) & np.isfinite(pos)]
            if len(pos) == 0:
                return None, np.zeros(len(series), dtype=bool)
            lo, hi = float(np.min(pos)), float(np.max(pos))
            if lo <= 0 or hi <= 0:
                return None, (series.to_numpy(dtype=float) >= floor) & np.isfinite(series)
            num_bins = _log_nbins(n_positive if n_positive is not None else len(pos))
            edges = np.logspace(np.log10(lo), np.log10(hi), num=num_bins + 1)
            return edges, (series.to_numpy(dtype=float) >= floor) & np.isfinite(series)

        def _histogram_log(series, edges):
            """Counts in log-spaced bins; series values must be >= floor (zeros excluded)."""
            pos = series.to_numpy(dtype=float)
            pos = pos[(pos >= _LOG_FLOOR) & np.isfinite(pos)]
            if len(pos) == 0:
                return np.zeros(len(edges) - 1), (edges[:-1] + edges[1:]) / 2
            counts, _ = np.histogram(pos, bins=edges)
            centers = (edges[:-1] + edges[1:]) / 2
            return counts, centers

        description = io.StringIO()

        # Calculate success rate and create title
        pSuccess = u.pc(len(df) / N)
        n_failed = N - len(df)
        print(f"Success rate: {pSuccess} on {N} scenarios.", file=description)
        if n_failed > 0:
            print(f"N failed: {n_failed}", file=description)
        title = f"N = {N}, P = {pSuccess}"

        # Calculate statistics
        means = df.mean(axis=0, numeric_only=True)
        medians = df.median(axis=0, numeric_only=True)

        # Handle mid-year cases
        my = 2 * [year_n[-1]]
        if N_i == 2 and n_d is not None and n_d < len(year_n):
            my[0] = year_n[n_d - 1]

        # Handle partial bequest cases
        if (phi_j is not None and np.all((1 - phi_j) < 0.01)) or medians.iloc[0] < 1:
            if medians.iloc[0] < 1:
                print(f"Optimized solutions all have null partial bequest in year {my[0]}.",
                      file=description)
            df.drop("partial", axis=1, inplace=True)
            means = df.mean(axis=0, numeric_only=True)
            medians = df.median(axis=0, numeric_only=True)
            my[0] = my[1]

        colors = ["orange", "green"]
        nfields = len(means)
        # Convert to thousands
        df /= 1000

        if len(df) > 0:
            thisyear = year_n[0]
            if log_x:
                print("Histogram: log-scale x-axis, log-spaced bins (zeros excluded).",
                      file=description)

            if objective == "maxBequest":
                # Single figure with both partial and final bequests
                fig = go.Figure()

                if log_x:
                    # Shared log-spaced edges from union of both columns
                    all_pos = []
                    for col in df.columns:
                        s = df[col]
                        all_pos.extend(s[(s >= _LOG_FLOOR) & np.isfinite(s)].tolist())
                    if all_pos:
                        all_pos = np.array(all_pos)
                        lo, hi = float(np.min(all_pos)), float(np.max(all_pos))
                        num_bins = _log_nbins(len(all_pos))
                        edges = np.logspace(np.log10(lo), np.log10(hi), num=num_bins + 1)
                        for i, col in enumerate(df.columns):
                            counts, centers = _histogram_log(df[col], edges)
                            dmedian = u.d(medians.iloc[i], latex=False)
                            dmean = u.d(means.iloc[i], latex=False)
                            label = f"{my[i]}: M: {dmedian}, <x>: {dmean}"
                            fig.add_trace(go.Bar(
                                x=centers, y=counts, name=label,
                                opacity=0.7, marker_color=colors[i]
                            ))
                    else:
                        log_x = False
                        for i, col in enumerate(df.columns):
                            dmedian = u.d(medians.iloc[i], latex=False)
                            dmean = u.d(means.iloc[i], latex=False)
                            label = f"{my[i]}: M: {dmedian}, <x>: {dmean}"
                            fig.add_trace(go.Histogram(
                                x=df[col], name=label, opacity=0.7, marker_color=colors[i]
                            ))
                else:
                    for i, col in enumerate(df.columns):
                        dmedian = u.d(medians.iloc[i], latex=False)
                        dmean = u.d(means.iloc[i], latex=False)
                        label = f"{my[i]}: M: {dmedian}, <x>: {dmean}"
                        fig.add_trace(go.Histogram(
                            x=df[col], name=label, opacity=0.7, marker_color=colors[i]
                        ))

                fig.update_layout(
                    title=objective,
                    xaxis_title=f"{thisyear} $k",
                    yaxis_title="Count",
                    template=self.template,
                    barmode="overlay",
                    showlegend=True,
                    legend=_LEGEND_BOTTOM
                )
                if log_x:
                    fig.update_xaxes(type="log")

                leads = [f"partial {my[0]}", f"  final {my[1]}"]
                leads = leads if nfields == 2 else leads[1:]

            elif nfields == 2:
                # Two separate histograms
                fig = make_subplots(
                    rows=1, cols=2,
                    subplot_titles=[f"partial {my[0]}", objective],
                    horizontal_spacing=0.1
                )

                cols = ["partial", objective]
                leads = [f"partial {my[0]}", objective]

                for i, col in enumerate(cols):
                    dmedian = u.d(medians.iloc[i], latex=False)
                    dmean = u.d(means.iloc[i], latex=False)
                    label = f"M: {dmedian}, <x>: {dmean}"
                    if log_x:
                        edges, _ = _log_spaced_edges(df[col])
                        if edges is not None:
                            counts, centers = _histogram_log(df[col], edges)
                            fig.add_trace(
                                go.Bar(x=centers, y=counts, name=label,
                                       marker_color=colors[i], showlegend=True),
                                row=1, col=i+1
                            )
                        else:
                            fig.add_trace(
                                go.Histogram(x=df[col], name=label,
                                             marker_color=colors[i], showlegend=True),
                                row=1, col=i+1
                            )
                    else:
                        fig.add_trace(
                            go.Histogram(x=df[col], name=label,
                                         marker_color=colors[i], showlegend=True),
                            row=1, col=i+1
                        )

                fig.update_layout(title=title, template=self.template, height=400, width=800)
                fig.update_yaxes(title_text="Count", row=1, col=1)
                fig.update_xaxes(title_text=f"{thisyear} $k", row=1, col=1)
                fig.update_xaxes(title_text=f"{thisyear} $k", row=1, col=2)
                if log_x:
                    fig.update_xaxes(type="log", row=1, col=1)
                    fig.update_xaxes(type="log", row=1, col=2)

            else:
                # Single histogram for net spending
                fig = go.Figure()

                dmedian = u.d(medians.iloc[0], latex=False)
                dmean = u.d(means.iloc[0], latex=False)
                label = f"M: {dmedian}, <x>: {dmean}"

                use_log_scale = False
                if log_x:
                    edges, _ = _log_spaced_edges(df[objective])
                    if edges is not None:
                        counts, centers = _histogram_log(df[objective], edges)
                        fig.add_trace(go.Bar(x=centers, y=counts, name=label, marker_color="orange"))
                        use_log_scale = True
                    else:
                        fig.add_trace(go.Histogram(x=df[objective], name=label, marker_color="orange"))
                else:
                    fig.add_trace(go.Histogram(x=df[objective], name=label, marker_color="orange"))

                fig.update_layout(
                    title=objective,
                    xaxis_title=f"{thisyear} $k",
                    yaxis_title="Count",
                    template=self.template,
                    showlegend=True,
                    legend=_LEGEND_BOTTOM
                )
                if use_log_scale:
                    fig.update_xaxes(type="log")

                leads = [objective]

            # Add statistics to description
            for q in range(nfields):
                print(f"{leads[q]:>12}: Median ({thisyear} $): {u.d(medians.iloc[q])}", file=description)
                print(f"{leads[q]:>12}:   Mean ({thisyear} $): {u.d(means.iloc[q])}", file=description)
                mmin = 1000 * df.iloc[:, q].min()
                mmax = 1000 * df.iloc[:, q].max()
                print(f"{leads[q]:>12}:           Range: {u.d(mmin)} - {u.d(mmax)}", file=description)

            return fig, description

        return None, description

    def plot_spending_by_year(self, objective, start_years, values, n_d, year_n):
        """Bar chart of optimal spending or bequest by historical start year (today's dollars)."""
        import io as _io
        thisyear = int(year_n[0])
        label = "Spending basis" if objective == "maxSpending" else "Bequest"
        mean_val = float(np.mean(values))

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=start_years.tolist(),
            y=(values / 1000).tolist(),
            name=label,
            marker_color="steelblue",
            opacity=0.75,
        ))
        fig.add_hline(y=mean_val / 1000, line_dash="dash", line_color="navy",
                      annotation_text=f"Mean {u.d(mean_val)}", annotation_position="top right")
        fig.update_layout(
            title=f"{label} by historical start year",
            xaxis_title="Historical start year",
            yaxis_title=f"{label} ({thisyear} $k)",
            yaxis_tickformat="$,.0f",
            template=self.template,
            showlegend=False,
        )
        description = _io.StringIO()
        print(f"{label} by start year: min {u.d(float(values.min()))}, "
              f"max {u.d(float(values.max()))}, mean {u.d(mean_val)}.", file=description)
        return fig, description

    def plot_stochastic_frontier(self, frontier_prob, frontier_g, frontier_shortfall,
                                 target_success_rate_pct, g_opt, year_n, start_years=None,
                                 with_longevity=False):
        """Efficient frontier: committed spending vs. shortfall probability, with target marked."""
        thisyear = int(year_n[0])
        frontier_type = "Historical" if start_years is not None else "Stochastic"
        shortfall_pct = 100.0 - target_success_rate_pct

        fig = make_subplots(rows=1, cols=2,
                            subplot_titles=("Success rate curve", "Efficient frontier"))

        fig.add_trace(go.Scatter(
            x=(frontier_prob * 100).tolist(), y=(frontier_g / 1000).tolist(),
            mode="lines", line=dict(color="steelblue", width=2),
            showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[shortfall_pct], y=[g_opt / 1000],
            mode="markers+text",
            name=f"{target_success_rate_pct:.0f}% success: {u.d(g_opt)}",
            marker=dict(color="firebrick", size=10),
            text=[f"{u.d(g_opt)}"],
            textposition="top right",
        ), row=1, col=1)
        fig.add_vline(x=shortfall_pct, line_dash="dash", line_color="firebrick",
                      opacity=0.5, row=1, col=1)

        idx = int(np.argmin(np.abs(frontier_g - g_opt)))
        sf_at_target = float(frontier_shortfall[idx]) / 1000

        fig.add_trace(go.Scatter(
            x=(frontier_shortfall / 1000).tolist(), y=(frontier_g / 1000).tolist(),
            mode="lines", line=dict(color="darkorange", width=2),
            showlegend=False,
        ), row=1, col=2)
        fig.add_trace(go.Scatter(
            x=[sf_at_target], y=[g_opt / 1000],
            mode="markers+text",
            name=f"{target_success_rate_pct:.0f}% success: {u.d(g_opt)}",
            marker=dict(color="firebrick", size=10),
            text=[f"{u.d(g_opt)}"],
            textposition="top right",
            showlegend=False,
        ), row=1, col=2)
        fig.add_vline(x=sf_at_target, line_dash="dash", line_color="firebrick",
                      opacity=0.5, row=1, col=2)

        fig.update_xaxes(title_text="Shortfall probability (%)", ticksuffix="%",
                         title_font_size=14, tickfont_size=11, row=1, col=1)
        fig.update_yaxes(title_text=f"Committed spending ({thisyear} $k)", tickprefix="$",
                         title_font_size=14, tickfont_size=11, row=1, col=1)
        fig.update_xaxes(title_text=f"Expected shortfall ({thisyear} $k)", tickprefix="$",
                         title_font_size=14, tickfont_size=11, row=1, col=2)
        fig.update_yaxes(title_text=f"Committed spending ({thisyear} $k)", tickprefix="$",
                         title_font_size=14, tickfont_size=11, row=1, col=2)
        fig.update_annotations(font_size=14)
        longevity_tag = " · longevity" if with_longevity else ""
        fig.update_layout(
            title=dict(text=f"{frontier_type} spending efficient frontier ({thisyear}$){longevity_tag}", font_size=20),
            template=self.template,
            legend={**_LEGEND_BOTTOM, "font": {"size": 14}},
        )
        return fig

    def plot_stochastic_cvar_vs_pos(self, frontier_prob, frontier_cvar, rho_star_pct, cvar_star,
                                    target_success_rate_pct, year_n):
        """CVaR vs Probability of Success curve with current target and optimal ρ* marked."""
        thisyear = int(year_n[0])
        pos_pct = (1.0 - frontier_prob) * 100

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pos_pct.tolist(), y=(frontier_cvar / 1000).tolist(),
            mode="lines", line=dict(color="steelblue", width=2),
            showlegend=False,
        ))
        fig.add_vline(x=target_success_rate_pct, line_dash="dot", line_color="firebrick",
                      opacity=0.6)
        fig.add_trace(go.Scatter(
            x=[rho_star_pct], y=[cvar_star / 1000],
            mode="markers+text",
            marker=dict(symbol="diamond", color="darkorange", size=12),
            text=[f"ρ*={rho_star_pct:.0f}%"],
            textposition="top left",
            showlegend=False,
        ))
        fig.update_xaxes(title_text="Probability of success (%)", ticksuffix="%",
                         title_font_size=14, tickfont_size=11)
        fig.update_yaxes(title_text=f"CVaR ({thisyear} $k)", tickprefix="$",
                         title_font_size=14, tickfont_size=11)
        fig.update_layout(
            title=dict(text=f"Tail risk (CVaR) vs probability of success ({thisyear}$)", font_size=20),
            template=self.template,
        )
        return fig

    def plot_stochastic_res_vs_cvar(self, frontier_cvar, res_values, rho_star_pct, res_star,
                                    cvar_star, cvar_at_target, year_n, floor_label="HSF"):
        """RES vs CVaR curve with current target and RES* marked."""
        thisyear = int(year_n[0])
        valid = ~np.isnan(res_values)
        x = frontier_cvar[valid] / 1000
        y = res_values[valid]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x.tolist(), y=y.tolist(),
            mode="lines", line=dict(color="darkorange", width=2),
            showlegend=False,
        ))
        fig.add_vline(x=cvar_at_target / 1000, line_dash="dot", line_color="firebrick",
                      opacity=0.6)
        fig.add_hline(y=res_star, line_dash="dash", line_color="darkorange", opacity=0.5)
        fig.add_trace(go.Scatter(
            x=[cvar_star / 1000], y=[res_star],
            mode="markers+text",
            marker=dict(symbol="diamond", color="darkorange", size=12),
            text=[f"RES*={res_star:.2f}"],
            textposition="top right",
            showlegend=False,
        ))
        fig.update_xaxes(title_text=f"CVaR ({thisyear} $k)", tickprefix="$",
                         title_font_size=14, tickfont_size=11)
        fig.update_yaxes(title_text="RES", title_font_size=14, tickfont_size=11)
        fig.update_layout(
            title=dict(text=f"Retirement Efficiency Score vs tail risk ({floor_label} floor)", font_size=20),
            template=self.template,
        )
        return fig

    def plot_stochastic_outcomes(self, start_years, bases, g_opt, target_success_rate_pct, year_n,
                                 with_longevity=False):
        """Bar chart of achieved spending by scenario.

        Historical mode: bars by start year (x = historical start year).
        MC mode: bars sorted by achieved spending (x = scenario percentile), works at any N.
        """
        thisyear = int(year_n[0])
        achieved = np.minimum(g_opt, bases)
        success = achieved >= g_opt - 1.0
        label = "Spending"
        longevity_tag = " · longevity" if with_longevity else ""
        is_historical = start_years is not None

        fig = go.Figure()
        if is_historical:
            x = start_years.tolist()
            if success.any():
                x_ok = [x[i] for i in range(len(x)) if success[i]]
                fig.add_trace(go.Bar(x=x_ok, y=(achieved[success] / 1000).tolist(),
                                     name="No shortfall", marker_color="mediumseagreen", opacity=0.8))
            if (~success).any():
                x_fail = [x[i] for i in range(len(x)) if not success[i]]
                fig.add_trace(go.Bar(x=x_fail, y=(achieved[~success] / 1000).tolist(),
                                     name="Shortfall", marker_color="tomato", opacity=0.8))
            fig.add_hline(y=g_opt / 1000, line_dash="dash", line_color="black",
                          annotation_text=f"Commitment {u.d(g_opt)}", annotation_position="top right")
            fig.update_xaxes(title_text="Historical start year", title_font_size=14, tickfont_size=11)
            fig.update_yaxes(title_text=f"Achieved {label.lower()} ({thisyear} $k)",
                             tickprefix="$", title_font_size=14, tickfont_size=11)
        else:
            # Sort scenarios from worst to best; x-axis = scenario percentile (0–100%)
            order = np.argsort(achieved)
            sorted_ach = achieved[order]
            sorted_ok = success[order]
            N = len(sorted_ach)
            pct = (np.arange(N) / N * 100).tolist()
            fail_mask = ~sorted_ok
            ok_mask = sorted_ok
            if fail_mask.any():
                fig.add_trace(go.Bar(
                    x=[pct[i] for i in range(N) if fail_mask[i]],
                    y=(sorted_ach[fail_mask] / 1000).tolist(),
                    name="Shortfall", marker_color="tomato", opacity=0.8,
                ))
            if ok_mask.any():
                fig.add_trace(go.Bar(
                    x=[pct[i] for i in range(N) if ok_mask[i]],
                    y=(sorted_ach[ok_mask] / 1000).tolist(),
                    name="No shortfall", marker_color="mediumseagreen", opacity=0.8,
                ))
            n_ok = int(success.sum())
            fig.add_hline(y=g_opt / 1000, line_dash="dash", line_color="black",
                          annotation_text=f"Commitment {u.d(g_opt)}  ({n_ok / N * 100:.0f}% success)",
                          annotation_position="top left")
            fig.update_xaxes(title_text="Scenario percentile", ticksuffix="%",
                             title_font_size=14, tickfont_size=11)
            fig.update_yaxes(title_text=f"Achieved {label.lower()} ({thisyear} $k)",
                             tickprefix="$", title_font_size=14, tickfont_size=11)

        fig.update_layout(
            title=dict(text=f"Scenario outcomes — {target_success_rate_pct:.0f}% target{longevity_tag}",
                       font_size=20),
            template=self.template,
            barmode="overlay",
            legend={**_LEGEND_BOTTOM, "font": {"size": 14}},
        )
        return fig

    def plot_survival_curves(self, sexes, current_ages, inames, table="SSA2025"):
        """Survival probability P(alive at age X) for each individual, plus joint for couples."""
        from ..data.mortality_tables import survival_pmf

        colors = ["steelblue", "darkorange"]
        fig = go.Figure()

        age_start = min(current_ages)
        survival_full = []

        for i, (sex, ca) in enumerate(zip(sexes, current_ages)):
            ages_i, pmf_i = survival_pmf(sex, ca, table=table)
            surv_i = np.concatenate([[1.0], 1.0 - np.cumsum(pmf_i[:-1])])
            n_prepend = ca - age_start
            full_surv = np.concatenate([np.ones(n_prepend), surv_i])
            survival_full.append(full_surv)
            fig.add_trace(go.Scatter(
                x=ages_i.tolist(), y=(surv_i * 100).tolist(),
                mode="lines", name=inames[i],
                line=dict(color=colors[i % len(colors)], width=2),
            ))

        if len(current_ages) == 2:
            ages_common = np.arange(age_start, age_start + len(survival_full[0]), dtype=int)
            joint_surv = 1.0 - np.prod([1.0 - s for s in survival_full], axis=0)
            fig.add_trace(go.Scatter(
                x=ages_common.tolist(), y=(joint_surv * 100).tolist(),
                mode="lines", name="Joint (last survivor)",
                line=dict(color="mediumpurple", width=2, dash="dot"),
            ))

        fig.update_xaxes(title_text="Age", title_font_size=14, tickfont_size=11)
        fig.update_yaxes(title_text="Probability of being alive (%)", ticksuffix="%",
                         title_font_size=14, tickfont_size=11, range=[0, 101])
        fig.update_layout(
            title=dict(text=f"Survival curves — {table}", font_size=20),
            template=self.template,
            legend={**_LEGEND_BOTTOM, "font": {"size": 14}},
        )
        return fig

    def plot_drawn_lifespans(self, drawn_lifespans, inames):
        """Histogram of drawn ages at death from longevity sampling, shape (S, N_i)."""
        colors = ["steelblue", "darkorange"]
        n_i = drawn_lifespans.shape[1]
        fig = go.Figure()

        median_lines = []
        for i in range(n_i):
            ages_i = drawn_lifespans[:, i]
            median_i = int(np.median(ages_i))
            median_lines.append(f"{median_i}  {inames[i]}")
            fig.add_trace(go.Histogram(
                x=ages_i.tolist(),
                name=inames[i],
                marker_color=colors[i % len(colors)],
                opacity=0.75,
                xbins=dict(size=1),
                bingroup=1,
            ))

        if n_i == 2:
            joint_ages = np.maximum(drawn_lifespans[:, 0], drawn_lifespans[:, 1])
            joint_median = int(np.median(joint_ages))
            median_lines.append(f"{joint_median}  Joint")
            fig.add_trace(go.Histogram(
                x=joint_ages.tolist(),
                name="Joint (last survivor)",
                marker_color="mediumpurple",
                opacity=0.5,
                xbins=dict(size=1),
                bingroup=1,
            ))

        annotation_colors = colors[:n_i] + (["mediumpurple"] if n_i == 2 else [])
        fig.add_annotation(
            text="<b>Medians</b>",
            xref="paper", yref="paper", x=0.02, y=0.99,
            xanchor="left", showarrow=False,
            font=dict(size=15, color="gray"),
        )
        for k, (line, color) in enumerate(zip(median_lines, annotation_colors)):
            fig.add_annotation(
                text=line,
                xref="paper", yref="paper", x=0.02, y=0.89 - k * 0.10,
                xanchor="left", showarrow=False,
                font=dict(size=15, color=color),
            )

        fig.update_xaxes(title_text="Age at death", title_font_size=14, tickfont_size=11)
        fig.update_yaxes(title_text="Number of scenarios", title_font_size=14, tickfont_size=11)
        fig.update_layout(
            title=dict(text="Drawn lifespans", font_size=20),
            template=self.template,
            barmode="overlay",
            legend={**_LEGEND_BOTTOM, "font": {"size": 14}},
        )
        return fig

    def plot_retention_margin(self, year_n, margin_n, title):
        """Diverging bar chart of retention margin above real break-even. Reference at 0."""
        title = title.replace("\n", "<br>")
        colors = ["steelblue" if (not np.isnan(m) and m > 0) else "tomato" for m in margin_n]
        fig = go.Figure(go.Bar(x=year_n, y=margin_n, marker_color=colors, opacity=0.85,
                               name="Retention margin",
                               hovertemplate="%{x}: %{y:+.1f} pp<extra></extra>"))
        fig.add_hline(y=0, line_width=1, line_color="black")
        fig.update_layout(
            title=title,
            yaxis_title="Retention margin (pp vs. break-even)",
            yaxis=dict(tickformat="+.1f", ticksuffix=" pp"),
            template=self.template,
        )
        return fig

    def plot_asset_composition(self, year_n, inames, b_ijkn, gamma_n, value, name, tag):
        """Plot asset distribution over time."""
        # Set up value formatting
        if value == "nominal":
            yformat = "$k (nominal)"
            infladjust = 1
        else:
            yformat = f"$k ({year_n[0]}$)"
            infladjust = gamma_n

        # Prepare years array
        years_n = np.array(year_n)
        years_n = np.append(years_n, [years_n[-1] + 1])

        # Define account and asset type mappings
        jDic = {"taxable": 0, "tax-deferred": 1, "tax-free": 2, "hsa": 3}
        kDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}

        figures = []
        for jkey in jDic:
            # Create figure for this account type
            fig = go.Figure()

            # Prepare data for stacking
            stack_data = []
            stack_names = []
            for kkey in kDic:
                namek = f"{kkey} / {jkey}"
                stack_names.append(namek)

                # Calculate values for each individual
                values = np.zeros((len(inames), len(years_n)))
                for i in range(len(inames)):
                    values[i] = b_ijkn[i][jDic[jkey]][kDic[kkey]] / infladjust

                # Add each individual's data as a separate series
                for i in range(len(inames)):
                    if np.abs(np.sum(values[i])) > 1.0:  # Only show non-zero series (use abs for debts)
                        stack_data.append((values[i], f"{namek} {inames[i]}"))

            # Skip account types with no data
            if not stack_data:
                figures.append(None)
                continue

            # Add stacked area traces
            for data, dname in stack_data:
                fig.add_trace(go.Scatter(
                    x=years_n,
                    y=data/1000,
                    name=dname,
                    stackgroup="one",
                    fill="tonexty",
                    opacity=0.6
                ))

            # Update layout
            title = f"{name}<br>Asset Composition - {jkey}"
            if tag:
                title += f" - {tag}"

            fig.update_layout(
                title=title,
                # xaxis_title="year",
                yaxis_title=yformat,
                template=self.template,
                showlegend=True,
                legend={**_LEGEND_BOTTOM, "y": -0.65},
                margin=dict(b=150)
            )

            # Format y-axis as k
            fig.update_yaxes(tickformat=",.0f")

            figures.append(fig)

        return figures

    def plot_allocations(self, year_n, inames, alpha_ijkn, ARCoord, title):
        """Plot allocations over time."""
        # Determine account types based on coordination
        if ARCoord == "spouses":
            acList = [ARCoord]
        elif ARCoord == "individual":
            acList = [ARCoord]
        elif ARCoord == "account":
            acList = ["taxable", "tax-deferred", "tax-free", "hsa"]
        else:
            raise ValueError(f"Unknown coordination {ARCoord}.")

        # Define asset type mapping
        assetDic = {"stocks": 0, "C bonds": 1, "T notes": 2, "common": 3}

        title = title.replace("\n", "<br>")
        figures = []
        icount = len(inames)
        for i in range(icount):
            for acType in acList:
                # Create figure for this account type
                fig = go.Figure()

                # Prepare data for stacking
                stack_data = []
                stack_names = []
                for key in assetDic:
                    # aname = f"{key} / {acType}"
                    aname = key
                    stack_names.append(aname)

                    # Get allocation data
                    data = 100*alpha_ijkn[i, acList.index(acType), assetDic[key], :len(year_n)]
                    stack_data.append(data)

                # Add stacked area traces
                for data, name in zip(stack_data, stack_names, strict=True):
                    fig.add_trace(go.Scatter(
                        x=year_n,
                        y=data,
                        name=name,
                        stackgroup="one",
                        fill="tonexty",
                        opacity=0.6
                    ))

                # Update layout
                plot_title = f"{title} - {acType} {inames[i]}"
                fig.update_layout(
                    title=plot_title,
                    # xaxis_title="year",
                    yaxis_title="%",
                    template=self.template,
                    showlegend=True,
                    legend=_LEGEND_BOTTOM_REVERSED,
                    margin=dict(b=150)
                )

                # Format y-axis as percentage
                fig.update_yaxes(tickformat=".0f")

                figures.append(fig)

        return figures

    def plot_accounts(self, year_n, savings_in, gamma_n, value, title, inames):
        """Plot accounts over time."""
        # Create figure
        fig = go.Figure()

        # Prepare years array
        year_n_full = np.append(year_n, [year_n[-1] + 1])

        # Set up value formatting
        if value == "nominal":
            yformat = "$k (nominal)"
            savings = savings_in
        else:
            yformat = f"$k ({year_n[0]}$)"
            savings = {k: v / gamma_n for k, v in savings_in.items()}

        # Filter out zero series and create individual series names
        nonzero_series = {}
        for sname in savings:
            for i in range(len(inames)):
                data = savings[sname][i] / 1000
                if np.abs(np.sum(data)) > 1.0e-3:  # Only show non-zero series (use abs for debts)
                    nonzero_series[f"{sname} {inames[i]}"] = data

        # Add stacked area traces for each account type
        for account_name, data in nonzero_series.items():
            fig.add_trace(go.Scatter(
                x=year_n_full,
                y=data,
                name=account_name,
                stackgroup="one",
                fill="tonexty",
                opacity=0.6
            ))

        title = title.replace("\n", "<br>")
        # Update layout
        fig.update_layout(
            title=title,
            # xaxis_title="year",
            yaxis_title=yformat,
            template=self.template,
            showlegend=True,
            legend=_LEGEND_BOTTOM_REVERSED,
            margin=dict(b=150)
        )

        # Format y-axis as currency
        fig.update_yaxes(tickformat=",.0f")

        return fig

    def plot_hsa(self, year_n, hsa_data, gamma_n, value, title, inames):
        """Plot HSA balance, contributions, and withdrawals over time."""
        year_n_full = np.append(year_n, [year_n[-1] + 1])
        if value == "nominal":
            yformat = "$k (nominal)"
            scale_full = 1.0
            scale = 1.0
        else:
            yformat = f"$k ({year_n[0]}$)"
            scale_full = gamma_n
            scale = gamma_n[:-1]

        _hsa_thr = 1.0e-3
        has_medicare = (
            "medicare_withdrawals" in hsa_data
            and np.max(np.abs(hsa_data["medicare_withdrawals"])) > 0
        )
        fig = go.Figure()
        title_html = title.replace("\n", "<br>")
        colors = [
            "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
            "#FFA15A", "#19D3F3", "#FF6692", "#B6E880",
        ]
        n_ind = len(inames)
        for i, iname in enumerate(inames):
            c = colors[i % len(colors)]
            mc = colors[(i + n_ind) % len(colors)]
            bal = hsa_data["balance"][i] / (scale_full * 1000)
            ctrb = hsa_data["contributions"][i] / (scale * 1000)
            wdrwl = hsa_data["withdrawals"][i] / (scale * 1000)
            if np.max(np.abs(bal)) > _hsa_thr:
                fig.add_trace(go.Scatter(
                    x=year_n_full, y=bal,
                    name=f"balance {iname}",
                    fill="tozeroy", opacity=0.4,
                    line=dict(color=c),
                ))
            if np.max(np.abs(ctrb)) > _hsa_thr:
                fig.add_trace(go.Scatter(
                    x=year_n, y=ctrb,
                    name=f"contributions {iname}",
                    line=dict(color=c, dash="dash"),
                ))
            if has_medicare:
                med = hsa_data["medicare_withdrawals"][i] / (scale * 1000)
                nonmed = wdrwl - med
                if np.max(np.abs(med)) > _hsa_thr:
                    fig.add_trace(go.Scatter(
                        x=year_n, y=med,
                        name=f"Medicare {iname}",
                        stackgroup=f"wdrwl_{i}",
                        opacity=0.65,
                        line=dict(color=mc, width=0),
                        fillcolor=mc,
                    ))
                if np.max(np.abs(nonmed)) > _hsa_thr:
                    fig.add_trace(go.Scatter(
                        x=year_n, y=nonmed,
                        name=f"QME {iname}",
                        stackgroup=f"wdrwl_{i}",
                        opacity=0.3,
                        line=dict(color=c, width=0),
                        fillcolor=c,
                    ))
            elif np.max(np.abs(wdrwl)) > _hsa_thr:
                fig.add_trace(go.Scatter(
                    x=year_n, y=wdrwl,
                    name=f"withdrawals {iname}",
                    line=dict(color=c, dash="dot"),
                ))

        fig.update_layout(
            title=title_html,
            yaxis_title=yformat,
            template=self.template,
            showlegend=True,
            legend=_LEGEND_BOTTOM,
            margin=dict(b=150),
        )
        fig.update_yaxes(tickformat=",.0f")
        return fig

    def plot_sources(self, year_n, sources_in, gamma_n, value, title, inames):
        """Plot sources over time."""
        # Create figure
        fig = go.Figure()

        # Set up value formatting
        if value == "nominal":
            yformat = "$k (nominal)"
            sources = sources_in
        else:
            yformat = f"$k ({year_n[0]}$)"
            sources = {k: v / gamma_n[:-1] for k, v in sources_in.items()}

        # Filter out zero series and create individual series names
        nonzero_series = {}
        for sname in sources:
            source_data = sources[sname]
            # Check if this is a household-level source (shape (1, N_n) when N_i > 1)
            is_household = source_data.shape[0] == 1 and len(inames) > 1
            if is_household:
                # Show household total once without individual name
                data = source_data[0] / 1000
                if np.abs(np.sum(data)) > 1.0e-3:  # Only show non-zero series (use abs for debts)
                    nonzero_series[sname] = data
            else:
                # Show per individual
                for i in range(len(inames)):
                    data = source_data[i] / 1000
                    if np.abs(np.sum(data)) > 1.0e-3:  # Only show non-zero series (use abs for debts)
                        nonzero_series[f"{sname} {inames[i]}"] = data

        # Add stacked area traces for each source type
        for source_name, data in nonzero_series.items():
            group = "negative" if np.sum(data) < 0 else "positive"
            fig.add_trace(go.Scatter(
                x=year_n,
                y=data,
                name=source_name,
                stackgroup=group,
                fill="tonexty",
                opacity=0.6
            ))

        title = title.replace("\n", "<br>")
        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title=yformat,
            template=self.template,
            showlegend=True,
            legend={**_LEGEND_BOTTOM_REVERSED, "y": -0.75},
            margin=dict(b=150)
        )

        # Format y-axis as k
        fig.update_yaxes(tickformat=",.0f")

        return fig

    def plot_lifetime_allocation(self, alloc, name):
        """Plot two pie charts: lifetime outflows breakdown and income sources."""
        outflow_labels_map = {
            "living":     "Living expenses",
            "taxes":      "Taxes",
            "state_taxes": "State taxes",
            "healthcare": "Healthcare",
            "debt":       "Debt payments",
            "bti":        "Big-ticket items",
            "bequest":    "Bequest",
            "heirtax":    "Est. heir taxes",
        }
        income_labels_map = {
            "portfolio":   "Portfolio",
            "ss":          "Social Security",
            "pension":     "Pension",
            "wages":       "Wages",
            "spia":        "SPIA",
            "fixedassets": "Fixed assets",
            "other":       "Other income",
            "bti":         "Big-ticket items",
        }

        def _pie_data(values_dict, labels_map, color_map):
            labels, values, colors = [], [], []
            for key, val in values_dict.items():
                if val > 0:
                    labels.append(labels_map[key])
                    values.append(val / 1000)
                    colors.append(color_map[key])
            return labels, values, colors

        out_labels, out_values, out_colors = _pie_data(alloc["outflows"], outflow_labels_map, _OUTFLOW_COLORS)
        inc_labels, inc_values, inc_colors = _pie_data(alloc["income"], income_labels_map, _INCOME_COLORS)

        if not out_values or not inc_values:
            return None

        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "pie"}, {"type": "pie"}]],
            subplot_titles=["Sources of income", "Outflows breakdown"],
        )
        fig.add_trace(go.Pie(
            labels=inc_labels, values=inc_values,
            marker_colors=inc_colors,
            textinfo="label+percent",
            hovertemplate="%{label}<br>$%{value:,.0f}k<br>%{percent}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Pie(
            labels=out_labels, values=out_values,
            marker_colors=out_colors,
            textinfo="label+percent",
            hovertemplate="%{label}<br>$%{value:,.0f}k<br>%{percent}<extra></extra>",
        ), row=1, col=2)
        fa_bequest = alloc.get("fa_bequest", 0.0)
        fa_note = f" (excl. ${fa_bequest/1000:,.0f}k fixed-asset bequest)" if fa_bequest > 0 else ""
        fig.update_layout(
            title=dict(
                text=name + "<br>Lifetime Cash Flow (today's $)" + fa_note,
                x=0.5, xanchor="center",
            ),
            template=self.template,
            showlegend=False,
        )
        return fig

    def plot_cashflow_mix(self, mix, name):
        """Plot annual cash flow breakdown as normalized stacked-area charts (%)."""
        outflow_labels = {
            "living":     "Living expenses",
            "taxes":      "Taxes",
            "state_taxes": "State taxes",
            "healthcare": "Healthcare",
            "debt":       "Debt payments",
            "bti":        "Big-ticket items",
        }
        # portfolio is first so it anchors the bottom of the income stack.
        income_labels = {
            "portfolio":   "Portfolio",
            "ss":          "Social Security",
            "pension":     "Pension",
            "wages":       "Wages",
            "spia":        "SPIA",
            "fixedassets": "Fixed assets",
            "other":       "Other income",
            "bti":         "Big-ticket items",
        }

        year_n = mix["year_n"]

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=["Sources of income", "Outflows breakdown"],
        )

        has_out, has_inc = False, False
        for key, label in income_labels.items():
            data = mix["income"].get(key)
            if data is not None and data.max() > 0:
                fig.add_trace(go.Scatter(
                    x=year_n, y=data,
                    name=label,
                    stackgroup="income",
                    groupnorm="percent",
                    fill="tonexty",
                    opacity=0.7,
                    marker_color=_INCOME_COLORS[key],
                    hovertemplate=f"{label}: %{{y:.1f}}%<extra></extra>",
                    legend="legend",
                    showlegend=True,
                ), row=1, col=1)
                has_inc = True

        for key, label in outflow_labels.items():
            data = mix["outflows"].get(key)
            if data is not None and data.max() > 0:
                fig.add_trace(go.Scatter(
                    x=year_n, y=data,
                    name=label,
                    stackgroup="outflows",
                    groupnorm="percent",
                    fill="tonexty",
                    opacity=0.7,
                    marker_color=_OUTFLOW_COLORS[key],
                    hovertemplate=f"{label}: %{{y:.1f}}%<extra></extra>",
                    legend="legend2",
                    showlegend=True,
                ), row=1, col=2)
                has_out = True

        if not has_out or not has_inc:
            return None

        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        fig.update_xaxes(tickformat="d")
        fig.update_layout(
            title=dict(
                text=name + "<br>Annual Cash Flow Mix (today's $, bequest excl.)",
                x=0.5, xanchor="center",
            ),
            template=self.template,
            showlegend=True,
            legend=dict(
                x=0.44, y=0.02, xanchor="right", yanchor="bottom",
                orientation="v",
                bgcolor="rgba(255,255,255,0.15)",
                bordercolor="rgba(128,128,128,0.3)",
                borderwidth=1,
            ),
            legend2=dict(
                x=0.98, y=0.02, xanchor="right", yanchor="bottom",
                orientation="v",
                bgcolor="rgba(255,255,255,0.15)",
                bordercolor="rgba(128,128,128,0.3)",
                borderwidth=1,
            ),
            margin=dict(b=60),
        )
        return fig
