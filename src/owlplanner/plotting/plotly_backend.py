"""
Plotly backend implementation for plotting retirement planning results.

This module provides the Plotly-based implementation of the plot backend
interface for creating interactive visualizations of retirement planning data.

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
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# import plotly.io as pio

import io
from scipy import stats

from .base import PlotBackend
from .. import utils as u


class PlotlyBackend(PlotBackend):
    """Plotly implementation of plot backend."""

    def __init__(self):
        """Initialize the plotly backend."""
        # Set default template and layout
        self.template = "plotly_white"
        self.layout = dict(
            showlegend=True,
            legend=dict(
                traceorder="reversed",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255, 255, 255, 0.5)"
            ),
            xaxis=dict(
                # title="year",
                showgrid=True,
                griddash="dot",
                gridcolor="lightgray",
                zeroline=True,
                zerolinecolor="gray",
                zerolinewidth=1
            ),
            yaxis=dict(
                showgrid=True,
                griddash="dot",
                gridcolor="lightgray",
                zeroline=True,
                zerolinecolor="gray",
                zerolinewidth=1
            )
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
            legend=dict(
                traceorder="reversed",
                yanchor="bottom",
                y=-0.5,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0, 0, 0, 0)",
                orientation="h"
            ),
            margin=dict(b=150)
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
            legend=dict(
                yanchor="bottom",
                y=-0.5,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0, 0, 0, 0)",
                orientation="h"
            ),
            margin=dict(b=150)
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
            legend=dict(
                yanchor="bottom",
                y=-0.4,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0, 0, 0, 0)",
                orientation="h"
            ),
            margin=dict(b=150)
        )

        # Format y-axis as k
        fig.update_yaxes(tickformat=",.0f")

        ymin = np.min(net_data)
        ymax = np.max(net_data)
        if np.abs(ymax - ymin) < 1:
            fig.update_layout(yaxis=dict(range=[np.floor(ymin)-1, np.ceil(ymax)+1]))

        return fig

    def plot_taxes(self, year_n, T_n, M_n, gamma_n, value, title, inames):
        """Plot taxes over time."""
        fig = go.Figure()

        # Calculate data based on value type
        if value == "nominal":
            income_tax_data = T_n / 1000
            medicare_data = M_n / 1000
            y_title = "$k (nominal)"
        else:
            income_tax_data = T_n / gamma_n[:-1] / 1000
            medicare_data = M_n / gamma_n[:-1] / 1000
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

        title = title.replace("\n", "<br>")
        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title=y_title,
            template=self.template,
            showlegend=True,
            legend=dict(
                yanchor="bottom",
                y=-0.4,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0, 0, 0, 0)",
                orientation="h"
            ),
            margin=dict(b=150)
        )

        # Format y-axis as currency
        fig.update_yaxes(tickformat=",.0f")

        return fig

    def plot_rates(self, name, tau_kn, year_n, N_k, rate_method, rate_frm=None, rate_to=None, tag=""):
        """Plot rate values used over the time horizon."""
        fig = go.Figure()

        # Build title
        title = name + "<br>Return & Inflation Rates (" + str(rate_method)
        if rate_method in ["historical", "histochastic", "historical average"]:
            title += f" {rate_frm}-{rate_to}"
        title += ")"
        if tag:
            title += " - " + tag

        # Define rate names and line styles
        rate_names = [
            "S&P500 (incl. div.)",
            "Baa Corp. Bonds",
            "10-y T-Notes",
            "Inflation",
        ]
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
            # xaxis_title="year",
            yaxis_title="%",
            template=self.template,
            showlegend=True,
            legend=dict(
                yanchor="bottom",
                y=-0.60,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0, 0, 0, 0)",
                orientation="h"
            ),
            margin=dict(b=150)
        )

        # Format y-axis as percentage
        fig.update_yaxes(tickformat=".1f")

        return fig

    def plot_rates_distributions(self, frm, to, SP500, BondsBaa, TNotes, Inflation, FROM):
        """Plot histograms of the rates distributions."""
        # Create subplot figure
        fig = make_subplots(
            rows=1, cols=4,
            subplot_titles=("S&P500", "BondsBaa", "TNotes", "Inflation"),
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
            mean_val = np.mean(dat)
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

    def plot_rates_correlations(self, pname, tau_kn, N_n, rate_method, rate_frm=None, rate_to=None,
                                tag="", share_range=False):
        """Plot correlations between various rates."""
        # Create DataFrame with rate data
        rate_names = [
            "S&P500 (incl. div.)",
            "Baa Corp. Bonds",
            "10-y T-Notes",
            "Inflation",
        ]

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
        title = pname + "<br>"
        title += f"Rates Correlations (N={N_n}) {rate_method}"
        if rate_method in ["historical", "histochastic"]:
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
                    legend=dict(
                        yanchor="bottom", y=-0.50, xanchor="center", x=0.5,
                        bgcolor="rgba(0, 0, 0, 0)"
                    )
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
                    legend=dict(
                        yanchor="bottom", y=-0.50, xanchor="center", x=0.5,
                        bgcolor="rgba(0, 0, 0, 0)"
                    )
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
        jDic = {"taxable": 0, "tax-deferred": 1, "tax-free": 2}
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
                legend=dict(
                    # traceorder="reversed",
                    yanchor="bottom",
                    y=-0.65,
                    xanchor="center",
                    x=0.5,
                    bgcolor="rgba(0, 0, 0, 0)",
                    orientation="h"
                ),
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
            acList = ["taxable", "tax-deferred", "tax-free"]
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
                    legend=dict(
                        traceorder="reversed",
                        yanchor="bottom",
                        y=-0.5,
                        xanchor="center",
                        x=0.5,
                        bgcolor="rgba(0, 0, 0, 0)",
                        orientation="h"
                    ),
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
            legend=dict(
                traceorder="reversed",
                yanchor="bottom",
                y=-0.5,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0, 0, 0, 0)",
                orientation="h"
            ),
            margin=dict(b=150)
        )

        # Format y-axis as currency
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
            fig.add_trace(go.Scatter(
                x=year_n,
                y=data,
                name=source_name,
                stackgroup="one",
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
            legend_traceorder="reversed",
            legend=dict(
                yanchor="bottom",
                y=-0.75,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0, 0, 0, 0)",
                orientation="h",
            ),
            margin=dict(b=150)
        )

        # Format y-axis as k
        fig.update_yaxes(tickformat=",.0f")

        return fig
