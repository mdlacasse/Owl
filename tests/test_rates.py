"""
Tests for rates module - Rates class and getRatesDistributions function.

Tests verify that the Rates class correctly handles different rate methods
and generates rate series as expected.

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

import pytest
import numpy as np
import pandas as pd

from owlplanner import rates
from owlplanner.rates import (
    FROM,
    TO,
    getRatesDistributions,
)


class TestRatesInitialization:
    """Tests for Rates class initialization."""

    def test_default_initialization(self):
        """Test that Rates initializes with default method."""
        r = rates.Rates()
        assert r.method == "default"
        assert len(r.means) == 4
        assert len(r.stdev) == 4
        assert r.corr.shape == (4, 4)
        assert r.covar.shape == (4, 4)
        assert r.frm == FROM
        assert r.to == TO

    def test_initialization_with_logger(self):
        """Test initialization with custom logger."""
        from owlplanner import mylogging
        mylog = mylogging.Logger(verbose=False)
        r = rates.Rates(mylog=mylog)
        assert r.mylog == mylog
        assert r.method == "default"

    def test_default_rates_values(self):
        """Test that default rates are set correctly."""
        r = rates.Rates()
        # Default rates should be approximately the predefined values
        expected_default = np.array([0.1101, 0.0736, 0.0503, 0.0251])
        np.testing.assert_array_almost_equal(r.means, expected_default, decimal=4)


class TestRatesSetMethod:
    """Tests for setMethod functionality."""

    def test_set_method_default(self):
        """Test setting method to default."""
        r = rates.Rates()
        means, stdev, corr = r.setMethod("default")
        assert r.method == "default"
        expected = np.array([0.1101, 0.0736, 0.0503, 0.0251])
        np.testing.assert_array_almost_equal(means, expected, decimal=4)

    def test_set_method_optimistic(self):
        """Test setting method to optimistic."""
        r = rates.Rates()
        means, stdev, corr = r.setMethod("optimistic")
        assert r.method == "optimistic"
        # Note: setMethod sets self.means to _defRates but uses _optimisticRates for actual rates
        # The returned means are _defRates, but the actual rates used are _optimisticRates
        expected_means = np.array([0.1101, 0.0736, 0.0503, 0.0251])  # _defRates
        np.testing.assert_array_almost_equal(means, expected_means, decimal=4)
        # Verify the actual rates used are optimistic
        series = r.genSeries(1)
        expected_rates = np.array([0.086, 0.049, 0.033, 0.025])  # _optimisticRates
        np.testing.assert_array_almost_equal(series[0], expected_rates, decimal=3)

    def test_set_method_conservative(self):
        """Test setting method to conservative."""
        r = rates.Rates()
        means, stdev, corr = r.setMethod("conservative")
        assert r.method == "conservative"
        expected = np.array([0.06, 0.04, 0.033, 0.028])
        np.testing.assert_array_almost_equal(means, expected, decimal=3)

    def test_set_method_user(self):
        """Test setting method to user with custom values."""
        r = rates.Rates()
        user_values = [8.0, 5.0, 3.5, 2.5]  # Percent values
        means, stdev, corr = r.setMethod("user", values=user_values)
        assert r.method == "user"
        # Values should be converted from percent to decimal
        expected = np.array(user_values) / 100.0
        np.testing.assert_array_almost_equal(means, expected, decimal=4)

    def test_set_method_user_missing_values(self):
        """Test that user method requires values."""
        r = rates.Rates()
        with pytest.raises(ValueError, match="Fixed values must be provided"):
            r.setMethod("user")

    def test_set_method_user_wrong_length(self):
        """Test that user method requires correct number of values."""
        r = rates.Rates()
        with pytest.raises(ValueError, match="Values must have 4 items"):
            r.setMethod("user", values=[8.0, 5.0])  # Only 2 values

    def test_set_method_historical(self):
        """Test setting method to historical."""
        r = rates.Rates()
        frm = 2000
        to = 2010
        means, stdev, corr = r.setMethod("historical", frm=frm, to=to)
        assert r.method == "historical"
        assert r.frm == frm
        assert r.to == to

    def test_set_method_historical_missing_frm(self):
        """Test that historical method requires frm parameter."""
        r = rates.Rates()
        with pytest.raises(ValueError, match="From year must be provided"):
            r.setMethod("historical")

    def test_set_method_historical_invalid_range(self):
        """Test that historical method validates year range."""
        r = rates.Rates()
        # frm out of bounds
        with pytest.raises(ValueError, match="out of bounds"):
            r.setMethod("historical", frm=1900, to=2000)
        # to out of bounds
        with pytest.raises(ValueError, match="out of bounds"):
            r.setMethod("historical", frm=2000, to=3000)
        # frm >= to
        with pytest.raises(ValueError, match="Unacceptable range"):
            r.setMethod("historical", frm=2000, to=2000)
        with pytest.raises(ValueError, match="Unacceptable range"):
            r.setMethod("historical", frm=2010, to=2000)

    def test_set_method_historical_average(self):
        """Test setting method to historical average."""
        r = rates.Rates()
        frm = 2000
        to = 2010
        means, stdev, corr = r.setMethod("historical average", frm=frm, to=to)
        assert r.method == "historical average"
        assert r.frm == frm
        assert r.to == to
        # Should have computed means, stdev, and corr
        assert len(means) == 4
        assert len(stdev) == 4
        assert corr.shape == (4, 4)

    def test_set_method_histochastic(self):
        """Test setting method to histochastic."""
        r = rates.Rates()
        frm = 2000
        to = 2010
        means, stdev, corr = r.setMethod("histochastic", frm=frm, to=to)
        assert r.method == "histochastic"
        assert r.frm == frm
        assert r.to == to
        # Should have computed means, stdev, and corr
        assert len(means) == 4
        assert len(stdev) == 4
        assert corr.shape == (4, 4)

    def test_set_method_stochastic(self):
        """Test setting method to stochastic."""
        r = rates.Rates()
        values = [8.0, 5.0, 3.5, 2.5]  # Percent
        stdev_vals = [15.0, 8.0, 5.0, 2.0]  # Percent
        means, stdev, corr = r.setMethod("stochastic", values=values, stdev=stdev_vals)
        assert r.method == "stochastic"
        # Values should be converted from percent to decimal
        expected_means = np.array(values) / 100.0
        expected_stdev = np.array(stdev_vals) / 100.0
        np.testing.assert_array_almost_equal(means, expected_means, decimal=4)
        np.testing.assert_array_almost_equal(stdev, expected_stdev, decimal=4)
        assert corr.shape == (4, 4)

    def test_set_method_stochastic_missing_values(self):
        """Test that stochastic method requires values."""
        r = rates.Rates()
        with pytest.raises(ValueError, match="Mean values must be provided"):
            r.setMethod("stochastic", stdev=[15.0, 8.0, 5.0, 2.0])

    def test_set_method_stochastic_missing_stdev(self):
        """Test that stochastic method requires stdev."""
        r = rates.Rates()
        with pytest.raises(ValueError, match="Standard deviations must be provided"):
            r.setMethod("stochastic", values=[8.0, 5.0, 3.5, 2.5])

    def test_set_method_stochastic_wrong_length(self):
        """Test that stochastic method validates array lengths."""
        r = rates.Rates()
        with pytest.raises(ValueError, match="Values must have 4 items"):
            r.setMethod("stochastic", values=[8.0, 5.0], stdev=[15.0, 8.0, 5.0, 2.0])
        with pytest.raises(ValueError, match="stdev must have 4 items"):
            r.setMethod("stochastic", values=[8.0, 5.0, 3.5, 2.5], stdev=[15.0, 8.0])

    def test_set_method_stochastic_with_full_correlation_matrix(self):
        """Test stochastic with full correlation matrix."""
        r = rates.Rates()
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        # Full 4x4 correlation matrix
        corr_matrix = np.array([
            [1.0, 0.3, 0.2, 0.1],
            [0.3, 1.0, 0.4, 0.2],
            [0.2, 0.4, 1.0, 0.3],
            [0.1, 0.2, 0.3, 1.0]
        ])
        means, stdev, corr = r.setMethod("stochastic", values=values, stdev=stdev_vals, corr=corr_matrix)
        assert corr.shape == (4, 4)
        np.testing.assert_array_almost_equal(corr, corr_matrix, decimal=4)

    def test_set_method_stochastic_with_off_diagonal_correlation(self):
        """Test stochastic with off-diagonal correlation values only."""
        r = rates.Rates()
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        # 6 off-diagonal values for 4x4 matrix: (4*3)/2 = 6
        off_diag = [0.3, 0.2, 0.1, 0.4, 0.2, 0.3]
        means, stdev, corr = r.setMethod("stochastic", values=values, stdev=stdev_vals, corr=off_diag)
        assert corr.shape == (4, 4)
        # Check symmetry
        assert np.allclose(corr, corr.T)
        # Check diagonal is 1
        assert np.allclose(np.diag(corr), 1.0)

    def test_set_method_stochastic_invalid_correlation_shape(self):
        """Test that stochastic method validates correlation matrix shape."""
        r = rates.Rates()
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        # Invalid shape
        with pytest.raises(RuntimeError, match="Unable to process correlation"):
            r.setMethod("stochastic", values=values, stdev=stdev_vals, corr=[0.3, 0.2])  # Wrong length

    def test_set_method_stochastic_asymmetric_correlation(self):
        """Test that correlation matrix must be symmetric."""
        r = rates.Rates()
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        # Asymmetric matrix
        corr_matrix = np.array([
            [1.0, 0.3, 0.2, 0.1],
            [0.5, 1.0, 0.4, 0.2],  # Different from [0,0]
            [0.2, 0.4, 1.0, 0.3],
            [0.1, 0.2, 0.3, 1.0]
        ])
        with pytest.raises(ValueError, match="Correlation matrix must be symmetric"):
            r.setMethod("stochastic", values=values, stdev=stdev_vals, corr=corr_matrix)

    def test_set_method_invalid_method(self):
        """Test that invalid method raises error."""
        r = rates.Rates()
        with pytest.raises(ValueError, match="Unknown rate selection method"):
            r.setMethod("invalid_method")


class TestRatesGenSeries:
    """Tests for genSeries functionality."""

    def test_gen_series_default(self):
        """Test generating series with default method."""
        r = rates.Rates()
        r.setMethod("default")
        N = 10
        series = r.genSeries(N)
        assert series.shape == (N, 4)
        # All rows should be the same for fixed rates
        for i in range(1, N):
            np.testing.assert_array_almost_equal(series[0], series[i], decimal=6)

    def test_gen_series_user(self):
        """Test generating series with user method."""
        r = rates.Rates()
        user_values = [8.0, 5.0, 3.5, 2.5]
        r.setMethod("user", values=user_values)
        N = 5
        series = r.genSeries(N)
        assert series.shape == (N, 4)
        # All rows should be the same for fixed rates
        expected = np.array(user_values) / 100.0
        for i in range(N):
            np.testing.assert_array_almost_equal(series[i], expected, decimal=4)

    def test_gen_series_historical(self):
        """Test generating series with historical method."""
        r = rates.Rates()
        frm = 2000
        to = 2010
        r.setMethod("historical", frm=frm, to=to)
        N = 5
        series = r.genSeries(N)
        assert series.shape == (N, 4)
        # Values should be in decimal (not percent)
        assert np.all(series < 1.0)  # Rates should be reasonable (< 100%)
        assert np.all(series > -1.0)  # Should not be extremely negative

    def test_gen_series_historical_wrapping(self):
        """Test that historical series wraps when N exceeds available years."""
        r = rates.Rates()
        frm = 2000
        to = 2005  # Only 6 years
        r.setMethod("historical", frm=frm, to=to)
        N = 10  # More than available years
        series = r.genSeries(N)
        assert series.shape == (N, 4)
        # Should wrap around - year 6 should repeat year 0
        np.testing.assert_array_almost_equal(series[0], series[6], decimal=4)

    def test_gen_series_historical_average(self):
        """Test generating series with historical average method."""
        r = rates.Rates()
        frm = 2000
        to = 2010
        r.setMethod("historical average", frm=frm, to=to)
        N = 5
        series = r.genSeries(N)
        assert series.shape == (N, 4)
        # All rows should be the same (average)
        for i in range(1, N):
            np.testing.assert_array_almost_equal(series[0], series[i], decimal=6)

    def test_gen_series_histochastic(self):
        """Test generating series with histochastic method."""
        r = rates.Rates()
        frm = 2000
        to = 2010
        r.setMethod("histochastic", frm=frm, to=to)
        N = 10
        series = r.genSeries(N)
        assert series.shape == (N, 4)
        # Values should be in decimal
        assert np.all(series < 1.0)
        # Different calls should produce different values (stochastic)
        series2 = r.genSeries(N)
        # Very unlikely to be identical (but possible)
        # Just check shape is correct
        assert series2.shape == (N, 4)

    def test_gen_series_stochastic(self):
        """Test generating series with stochastic method."""
        r = rates.Rates()
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        r.setMethod("stochastic", values=values, stdev=stdev_vals)
        N = 10
        series = r.genSeries(N)
        assert series.shape == (N, 4)
        # Values should be in decimal
        assert np.all(series < 1.0)
        # Different calls should produce different values
        series2 = r.genSeries(N)
        assert series2.shape == (N, 4)


class TestRatesDataframeWithPlan:
    """Integration tests for dataframe method with Plan."""

    def test_plan_set_rates_dataframe(self):
        """Test Plan.setRates with dataframe method (sequential rates, optional offset)."""
        import owlplanner as owl

        p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
        p.setSpendingProfile("flat")
        p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
        p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])

        n_years = p.N_n
        df = pd.DataFrame({
            "S&P 500": [10.0] * n_years,
            "Bonds Baa": [4.0] * n_years,
            "TNotes": [3.0] * n_years,
            "Inflation": [2.5] * n_years,
        })
        p.setRates("dataframe", df=df)

        assert p.rateMethod == "dataframe"
        assert p.tau_kn.shape[0] == 4
        assert p.tau_kn.shape[1] == p.N_n
        # First year should be 10%, 4%, 3%, 2.5% in decimal
        np.testing.assert_array_almost_equal(
            p.tau_kn[:, 0], [0.10, 0.04, 0.03, 0.025], decimal=6
        )

    def test_plan_set_rates_dataframe_with_offset(self):
        """Test Plan.setRates with dataframe method and offset."""
        import owlplanner as owl

        p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
        p.setSpendingProfile("flat")
        p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
        p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])

        n_years = p.N_n
        offset = 5
        df = pd.DataFrame({
            "S&P 500": [1.0] * offset + [10.0] * n_years,
            "Bonds Baa": [1.0] * offset + [4.0] * n_years,
            "TNotes": [1.0] * offset + [3.0] * n_years,
            "Inflation": [1.0] * offset + [2.5] * n_years,
        })
        p.setRates("dataframe", df=df, offset=offset)

        assert p.rateMethod == "dataframe"
        np.testing.assert_array_almost_equal(
            p.tau_kn[:, 0], [0.10, 0.04, 0.03, 0.025], decimal=6
        )


class TestGetRatesDistributions:
    """Tests for getRatesDistributions function."""

    def test_get_rates_distributions_basic(self):
        """Test basic functionality of getRatesDistributions."""
        frm = 2000
        to = 2010
        means, stdev, corr, covar = getRatesDistributions(frm, to)

        assert len(means) == 4
        assert len(stdev) == 4
        assert corr.shape == (4, 4)
        assert covar.shape == (4, 4)

        # Values should be in decimal (not percent)
        assert np.all(means < 1.0)
        assert np.all(stdev < 1.0)

        # Correlation matrix should be symmetric
        assert np.allclose(corr, corr.T)

        # Diagonal of correlation should be 1
        assert np.allclose(np.diag(corr), 1.0)

        # Correlation values should be in [-1, 1]
        assert np.all(corr >= -1.0)
        assert np.all(corr <= 1.0)

    def test_get_rates_distributions_with_logger(self):
        """Test getRatesDistributions with custom logger."""
        from owlplanner import mylogging
        mylog = mylogging.Logger(verbose=False)
        frm = 2000
        to = 2010
        means, stdev, corr, covar = getRatesDistributions(frm, to, mylog=mylog)
        assert len(means) == 4

    def test_get_rates_distributions_invalid_range(self):
        """Test that getRatesDistributions validates range."""
        # frm out of bounds
        with pytest.raises(ValueError, match="out of bounds"):
            getRatesDistributions(1900, 2000)
        # to out of bounds
        with pytest.raises(ValueError, match="out of bounds"):
            getRatesDistributions(2000, 3000)
        # frm >= to
        with pytest.raises(ValueError, match="must be smaller"):
            getRatesDistributions(2000, 2000)
        with pytest.raises(ValueError, match="must be smaller"):
            getRatesDistributions(2010, 2000)

    def test_get_rates_distributions_different_ranges(self):
        """Test getRatesDistributions with different year ranges."""
        # Short range
        means1, stdev1, corr1, covar1 = getRatesDistributions(2000, 2005)
        # Longer range
        means2, stdev2, corr2, covar2 = getRatesDistributions(2000, 2010)

        # Both should return valid results
        assert len(means1) == 4
        assert len(means2) == 4
        # Results should be different (different data ranges)
        assert not np.allclose(means1, means2, atol=1e-6)

    def test_get_rates_distributions_correlation_properties(self):
        """Test that correlation matrix has correct properties."""
        frm = 2000
        to = 2010
        means, stdev, corr, covar = getRatesDistributions(frm, to)

        # Check symmetry
        assert np.allclose(corr, corr.T)

        # Check diagonal is 1
        assert np.allclose(np.diag(corr), 1.0)

        # Check bounds
        assert np.all(corr >= -1.0)
        assert np.all(corr <= 1.0)

        # Check covariance matrix properties
        assert np.allclose(covar, covar.T)  # Symmetric
        # Diagonal should be variance (stdev^2)
        variances = np.diag(covar)
        expected_variances = stdev ** 2
        np.testing.assert_array_almost_equal(variances, expected_variances, decimal=4)


class TestRatesEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_set_method_multiple_times(self):
        """Test setting method multiple times."""
        r = rates.Rates()
        r.setMethod("default")
        assert r.method == "default"
        r.setMethod("optimistic")
        assert r.method == "optimistic"
        r.setMethod("conservative")
        assert r.method == "conservative"

    def test_gen_series_zero_length(self):
        """Test generating series with zero length."""
        r = rates.Rates()
        r.setMethod("default")
        series = r.genSeries(0)
        assert series.shape == (0, 4)

    def test_gen_series_single_year(self):
        """Test generating series for single year."""
        r = rates.Rates()
        r.setMethod("default")
        series = r.genSeries(1)
        assert series.shape == (1, 4)

    def test_historical_range_at_boundaries(self):
        """Test historical method at year boundaries."""
        r = rates.Rates()
        # At FROM boundary
        r.setMethod("historical", frm=FROM, to=FROM + 10)
        series = r.genSeries(5)
        assert series.shape == (5, 4)

        # At TO boundary
        r.setMethod("historical", frm=TO - 10, to=TO)
        series = r.genSeries(5)
        assert series.shape == (5, 4)

    def test_stochastic_with_identity_correlation(self):
        """Test stochastic method with identity correlation (no correlation)."""
        r = rates.Rates()
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        # No correlation matrix provided - should use identity
        means, stdev, corr = r.setMethod("stochastic", values=values, stdev=stdev_vals)
        # Should be identity matrix
        assert np.allclose(corr, np.eye(4))
