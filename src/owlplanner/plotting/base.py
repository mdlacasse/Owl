"""
Base classes for plot backends.
"""

from abc import ABC, abstractmethod


class PlotBackend(ABC):
    """Abstract base class for plot backends."""

    @abstractmethod
    def jupyter_renderer(self, fig):
        """Render plot for Jupyter."""
        pass

    @abstractmethod
    def plot_histogram_results(self, objective, df, N, year_n, n_d=None, N_i=1, phi_j=None):
        """Show a histogram of values from historical data or Monte Carlo simulations."""
        pass

    @abstractmethod
    def plot_rates_correlations(self, name, tau_kn, N_n, rate_method, rate_frm=None, rate_to=None,
                                tag="", share_range=False):
        """Plot correlations between various rates."""
        pass

    @abstractmethod
    def plot_rates(self, name, tau_kn, year_n, N_k, rate_method,
                   rate_frm=None, rate_to=None, tag=""):
        """Plot rate values used over the time horizon."""
        pass

    @abstractmethod
    def plot_rates_distributions(self, frm, to, SP500, BondsBaa, TNotes, Inflation, FROM):
        """Plot histograms of the rates distributions."""
        pass

    @abstractmethod
    def plot_gross_income(self, year_n, G_n, gamma_n, value, title, tax_brackets):
        """Plot gross income over time."""
        pass

    @abstractmethod
    def plot_profile(self, year_n, xi_n, title, inames):
        """Plot profile over time."""
        pass

    @abstractmethod
    def plot_net_spending(self, year_n, g_n, xi_n, xiBar_n, gamma_n, value, title, inames):
        """Plot net spending over time."""
        pass

    @abstractmethod
    def plot_asset_composition(self, year_n, inames, b_ijkn, gamma_n, value, name, tag):
        """Plot asset composition over time."""
        pass

    @abstractmethod
    def plot_allocations(self, year_n, inames, alpha_ijkn, ARCoord, title):
        """Plot allocations over time."""
        pass

    @abstractmethod
    def plot_accounts(self, year_n, savings_in, gamma_n, value, title, inames):
        """Plot accounts over time."""
        pass

    @abstractmethod
    def plot_sources(self, year_n, sources_in, gamma_n, value, title, inames):
        """Plot sources over time."""
        pass

    @abstractmethod
    def plot_taxes(self, year_n, T_n, M_n, gamma_n, value, title, inames):
        """Plot taxes over time."""
        pass
