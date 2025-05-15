"""
Plotly implementation of plot backend.
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
            name="income taxes",
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

    def plot_rates(self, name, tau_kn, year_n, year_frac_left, N_k, rate_method, rate_frm=None, rate_to=None, tag=""):
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
            # Don't plot partial rates for current year if mid-year
            if year_frac_left == 1:
                data = 100 * tau_kn[k]
                years = year_n
            else:
                data = 100 * tau_kn[k, 1:]
                years = year_n[1:]

            # Calculate mean and std
            mean_val = np.mean(data)
            std_val = np.std(data, ddof=1)  # Use ddof=1 to match pandas
            label = f"{rate_names[k]} <{mean_val:.1f} +/- {std_val:.1f}%>"

            # Add trace
            fig.add_trace(go.Scatter(
                x=years,
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

    def plot_histogram_results(self, objective, df, N, year_n, n_d=None, N_i=1, phi_j=None):
        """Show a histogram of values from historical data or Monte Carlo simulations."""
        description = io.StringIO()

        # Calculate success rate and create title
        pSuccess = u.pc(len(df) / N)
        print(f"Success rate: {pSuccess} on {N} samples.", file=description)
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

        # Convert to thousands
        df /= 1000

        if len(df) > 0:
            thisyear = year_n[0]

            if objective == "maxBequest":
                # Single figure with both partial and final bequests
                fig = go.Figure()

                # Add histograms for each column
                for i, col in enumerate(df.columns):
                    dmedian = u.d(medians.iloc[i], latex=False)
                    dmean = u.d(means.iloc[i], latex=False)
                    label = f"{my[i]}: M: {dmedian}, <x>: {dmean}"

                    # Add histogram
                    fig.add_trace(go.Histogram(
                        x=df[col],
                        name=label,
                        opacity=0.7,
                        marker_color="orange"
                    ))

                # Update layout
                fig.update_layout(
                    title=objective,
                    xaxis_title=f"{thisyear} $k",
                    yaxis_title="Count",
                    template=self.template,
                    barmode="overlay",
                    showlegend=True,
                    legend=dict(
                        yanchor="bottom",
                        y=-0.50,
                        xanchor="center",
                        x=0.5,
                        bgcolor="rgba(0, 0, 0, 0)"
                    )
                )

                leads = [f"partial {my[0]}", f"  final {my[1]}"]

            elif len(means) == 2:
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

                    # Add histogram
                    fig.add_trace(
                        go.Histogram(
                            x=df[col],
                            name=label,
                            marker_color="orange",
                            showlegend=False
                        ),
                        row=1, col=i+1
                    )

                    # Add statistics annotation
                    fig.add_annotation(
                        x=0.01, y=0.99,
                        xref=f"x{i+1}",
                        yref="paper",
                        text=label,
                        showarrow=False,
                        font=dict(size=10),
                        bgcolor="rgba(0, 0, 0, 0)"
                    )

                # Update layout
                fig.update_layout(
                    title=title,
                    template=self.template,
                    height=400,
                    width=800
                )

                # Update y-axis labels
                fig.update_yaxes(title_text="Count", row=1, col=1)
                fig.update_yaxes(title_text="Count", row=1, col=2)

            else:
                # Single histogram for net spending
                fig = go.Figure()

                dmedian = u.d(medians.iloc[0], latex=False)
                dmean = u.d(means.iloc[0], latex=False)
                label = f"M: {dmedian}, <x>: {dmean}"

                # Add histogram
                fig.add_trace(go.Histogram(
                    x=df[objective],
                    name=label,
                    marker_color="orange"
                ))

                # Update layout
                fig.update_layout(
                    title=objective,
                    xaxis_title=f"{thisyear} $k",
                    yaxis_title="Count",
                    template=self.template,
                    showlegend=True,
                    legend=dict(
                        yanchor="bottom",
                        y=-0.50,
                        xanchor="center",
                        x=0.5,
                        bgcolor="rgba(0, 0, 0, 0)"
                    )
                )

                leads = [objective]

            # Add statistics to description
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

    def plot_asset_distribution(self, year_n, inames, b_ijkn, gamma_n, value, name, tag):
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
                    if np.sum(values[i]) > 1.0:  # Only show non-zero series
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
            title = f"{name}<br>Assets Distribution - {jkey}"
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
                    aname = f"{key} / {acType}"
                    stack_names.append(aname)

                    # Get allocation data
                    data = 100*alpha_ijkn[i, acList.index(acType), assetDic[key], :len(year_n)]
                    stack_data.append(data)

                # Add stacked area traces
                for data, name in zip(stack_data, stack_names):
                    fig.add_trace(go.Scatter(
                        x=year_n,
                        y=data,
                        name=name,
                        stackgroup="one",
                        fill="tonexty",
                        opacity=0.6
                    ))

                # Update layout
                plot_title = f"{title} - {acType}"
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
                if np.sum(data) > 1.0e-3:  # Only show non-zero series
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
            for i in range(len(inames)):
                data = sources[sname][i] / 1000
                if np.sum(data) > 1.0e-3:  # Only show non-zero series
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
