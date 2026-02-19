"""
Tests for rates module - BuiltinRateModel and getRatesDistributions function.

Tests verify that built-in rate methods correctly generate rate series
via Plan.setRates and BuiltinRateModel. The legacy Rates class has been
deprecated; use Plan.setRates() as the single API.

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

from owlplanner.rate_models.builtin import BuiltinRateModel
from owlplanner.rates import (
    FROM,
    TO,
    getRatesDistributions,
)


def _model_config(method, **kwargs):
    """Build config dict for BuiltinRateModel."""
    cfg = {"method": method}
    cfg.update(kwargs)
    return cfg


class TestBuiltinRateModelInitialization:
    """Tests for BuiltinRateModel initialization and default method."""

    def test_default_initialization(self):
        """Test that BuiltinRateModel defaults produce expected rates."""
        m = BuiltinRateModel(_model_config("default"))
        series = m.generate(5)
        assert series.shape == (5, 4)
        expected = np.array([0.1101, 0.0736, 0.0503, 0.0251])
        np.testing.assert_array_almost_equal(series[0], expected, decimal=4)

    def test_initialization_with_logger(self):
        """Test initialization with custom logger."""
        from owlplanner import mylogging
        mylog = mylogging.Logger(verbose=False)
        m = BuiltinRateModel(_model_config("default"), logger=mylog)
        series = m.generate(1)
        assert series.shape == (1, 4)

    def test_default_rates_values(self):
        """Test that default rates match predefined values."""
        m = BuiltinRateModel(_model_config("default"))
        series = m.generate(1)
        expected = np.array([0.1101, 0.0736, 0.0503, 0.0251])
        np.testing.assert_array_almost_equal(series[0], expected, decimal=4)


class TestBuiltinRateModelMethods:
    """Tests for built-in rate methods."""

    def test_set_method_default(self):
        """Test default method."""
        m = BuiltinRateModel(_model_config("default"))
        series = m.generate(5)
        expected = np.array([0.1101, 0.0736, 0.0503, 0.0251])
        np.testing.assert_array_almost_equal(series[0], expected, decimal=4)

    def test_set_method_optimistic(self):
        """Test optimistic method."""
        m = BuiltinRateModel(_model_config("optimistic"))
        series = m.generate(1)
        expected = np.array([0.086, 0.049, 0.033, 0.025])
        np.testing.assert_array_almost_equal(series[0], expected, decimal=3)

    def test_set_method_conservative(self):
        """Test conservative method."""
        m = BuiltinRateModel(_model_config("conservative"))
        series = m.generate(1)
        expected = np.array([0.06, 0.04, 0.033, 0.028])
        np.testing.assert_array_almost_equal(series[0], expected, decimal=3)

    def test_set_method_user(self):
        """Test user method with custom values."""
        user_values = [8.0, 5.0, 3.5, 2.5]  # Percent values
        m = BuiltinRateModel(_model_config("user", values=user_values))
        series = m.generate(1)
        expected = np.array(user_values) / 100.0
        np.testing.assert_array_almost_equal(series[0], expected, decimal=4)

    def test_set_method_user_missing_values(self):
        """Test that user method requires values."""
        with pytest.raises(ValueError, match="requires parameter 'values'"):
            BuiltinRateModel(_model_config("user"))

    def test_set_method_user_wrong_length(self):
        """Test that user method requires correct number of values."""
        with pytest.raises(ValueError, match="Values must have 4 items"):
            BuiltinRateModel(_model_config("user", values=[8.0, 5.0]))

    def test_set_method_historical(self):
        """Test historical method."""
        frm, to = 2000, 2010
        m = BuiltinRateModel(_model_config("historical", frm=frm, to=to))
        series = m.generate(5)
        assert series.shape == (5, 4)
        assert np.all(series < 1.0)
        assert np.all(series > -1.0)

    def test_set_method_historical_missing_frm(self):
        """Test that historical method requires frm parameter."""
        with pytest.raises(ValueError, match="requires parameter 'frm'"):
            BuiltinRateModel(_model_config("historical"))

    def test_set_method_historical_invalid_range(self):
        """Test that historical method validates year range."""
        with pytest.raises(ValueError, match="out of bounds"):
            BuiltinRateModel(_model_config("historical", frm=1900, to=2000))
        with pytest.raises(ValueError, match="out of bounds"):
            BuiltinRateModel(_model_config("historical", frm=2000, to=3000))
        with pytest.raises(ValueError, match="Unacceptable range"):
            BuiltinRateModel(_model_config("historical", frm=2000, to=2000))
        with pytest.raises(ValueError, match="Unacceptable range"):
            BuiltinRateModel(_model_config("historical", frm=2010, to=2000))

    def test_set_method_historical_average(self):
        """Test historical average method."""
        frm, to = 2000, 2010
        m = BuiltinRateModel(_model_config("historical average", frm=frm, to=to))
        series = m.generate(5)
        assert series.shape == (5, 4)
        for i in range(1, 5):
            np.testing.assert_array_almost_equal(series[0], series[i], decimal=6)

    def test_set_method_histochastic(self):
        """Test histochastic method."""
        frm, to = 2000, 2010
        m = BuiltinRateModel(_model_config("histochastic", frm=frm, to=to), seed=42)
        series = m.generate(10)
        assert series.shape == (10, 4)
        assert np.all(series < 1.0)

    def test_set_method_stochastic(self):
        """Test stochastic method."""
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        m = BuiltinRateModel(
            _model_config("stochastic", values=values, stdev=stdev_vals),
            seed=42,
        )
        series = m.generate(5)
        assert series.shape == (5, 4)
        assert m.params["corr"].shape == (4, 4)

    def test_set_method_stochastic_missing_values(self):
        """Test that stochastic method requires values."""
        with pytest.raises(ValueError, match="requires parameter 'values'"):
            BuiltinRateModel(_model_config("stochastic", stdev=[15.0, 8.0, 5.0, 2.0]))

    def test_set_method_stochastic_missing_stdev(self):
        """Test that stochastic method requires stdev."""
        with pytest.raises(ValueError, match="requires parameter 'stdev'"):
            BuiltinRateModel(_model_config("stochastic", values=[8.0, 5.0, 3.5, 2.5]))

    def test_set_method_stochastic_with_full_correlation_matrix(self):
        """Test stochastic with full correlation matrix."""
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        corr_matrix = [
            [1.0, 0.3, 0.2, 0.1],
            [0.3, 1.0, 0.4, 0.2],
            [0.2, 0.4, 1.0, 0.3],
            [0.1, 0.2, 0.3, 1.0],
        ]
        m = BuiltinRateModel(
            _model_config("stochastic", values=values, stdev=stdev_vals, corr=corr_matrix),
            seed=42,
        )
        series = m.generate(5)
        assert series.shape == (5, 4)
        np.testing.assert_array_almost_equal(m.params["corr"], np.array(corr_matrix), decimal=4)

    def test_set_method_stochastic_with_off_diagonal_correlation(self):
        """Test stochastic with off-diagonal correlation values only."""
        values = [8.0, 5.0, 3.5, 2.5]
        stdev_vals = [15.0, 8.0, 5.0, 2.0]
        off_diag = [0.3, 0.2, 0.1, 0.4, 0.2, 0.3]
        m = BuiltinRateModel(
            _model_config("stochastic", values=values, stdev=stdev_vals, corr=off_diag),
            seed=42,
        )
        series = m.generate(5)
        assert series.shape == (5, 4)
        corr = m.params["corr"]
        assert np.allclose(corr, corr.T)
        assert np.allclose(np.diag(corr), 1.0)

    def test_set_method_stochastic_invalid_correlation_shape(self):
        """Test that stochastic method validates correlation matrix shape."""
        with pytest.raises(RuntimeError, match="Unable to process correlation"):
            BuiltinRateModel(
                _model_config(
                    "stochastic",
                    values=[8.0, 5.0, 3.5, 2.5],
                    stdev=[15.0, 8.0, 5.0, 2.0],
                    corr=[0.3, 0.2],
                ),
            )

    def test_set_method_stochastic_asymmetric_correlation(self):
        """Test that correlation matrix must be symmetric."""
        corr_matrix = [
            [1.0, 0.3, 0.2, 0.1],
            [0.5, 1.0, 0.4, 0.2],  # Asymmetric
            [0.2, 0.4, 1.0, 0.3],
            [0.1, 0.2, 0.3, 1.0],
        ]
        with pytest.raises(ValueError, match="symmetric"):
            BuiltinRateModel(
                _model_config(
                    "stochastic",
                    values=[8.0, 5.0, 3.5, 2.5],
                    stdev=[15.0, 8.0, 5.0, 2.0],
                    corr=corr_matrix,
                ),
            )

    def test_set_method_invalid_method(self):
        """Test that invalid method raises error."""
        with pytest.raises(ValueError, match="Unknown builtin rate method"):
            BuiltinRateModel(_model_config("invalid_method"))


class TestBuiltinRateModelGenSeries:
    """Tests for rate series generation."""

    def test_gen_series_default(self):
        """Test generating series with default method."""
        m = BuiltinRateModel(_model_config("default"))
        N = 10
        series = m.generate(N)
        assert series.shape == (N, 4)
        for i in range(1, N):
            np.testing.assert_array_almost_equal(series[0], series[i], decimal=6)

    def test_gen_series_user(self):
        """Test generating series with user method."""
        user_values = [8.0, 5.0, 3.5, 2.5]
        m = BuiltinRateModel(_model_config("user", values=user_values))
        N = 5
        series = m.generate(N)
        assert series.shape == (N, 4)
        expected = np.array(user_values) / 100.0
        for i in range(N):
            np.testing.assert_array_almost_equal(series[i], expected, decimal=4)

    def test_gen_series_historical(self):
        """Test generating series with historical method."""
        m = BuiltinRateModel(_model_config("historical", frm=2000, to=2010))
        N = 5
        series = m.generate(N)
        assert series.shape == (N, 4)
        assert np.all(series < 1.0)
        assert np.all(series > -1.0)

    def test_gen_series_historical_wrapping(self):
        """Test that historical series wraps when N exceeds available years."""
        m = BuiltinRateModel(_model_config("historical", frm=2000, to=2005))
        N = 10
        series = m.generate(N)
        assert series.shape == (N, 4)
        np.testing.assert_array_almost_equal(series[0], series[6], decimal=4)

    def test_gen_series_historical_average(self):
        """Test generating series with historical average method."""
        m = BuiltinRateModel(_model_config("historical average", frm=2000, to=2010))
        N = 5
        series = m.generate(N)
        assert series.shape == (N, 4)
        for i in range(1, N):
            np.testing.assert_array_almost_equal(series[0], series[i], decimal=6)

    def test_gen_series_histochastic(self):
        """Test generating series with histochastic method."""
        m = BuiltinRateModel(_model_config("histochastic", frm=2000, to=2010), seed=42)
        N = 10
        series = m.generate(N)
        assert series.shape == (N, 4)
        assert np.all(series < 1.0)

    def test_gen_series_stochastic(self):
        """Test generating series with stochastic method."""
        m = BuiltinRateModel(
            _model_config("stochastic", values=[8.0, 5.0, 3.5, 2.5], stdev=[15.0, 8.0, 5.0, 2.0]),
            seed=42,
        )
        N = 10
        series = m.generate(N)
        assert series.shape == (N, 4)
        assert np.all(series < 1.0)


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
            "T-Notes": [3.0] * n_years,
            "Inflation": [2.5] * n_years,
        })
        p.setRates("dataframe", df=df)

        assert p.rateMethod == "dataframe"
        assert p.tau_kn.shape[0] == 4
        assert p.tau_kn.shape[1] == p.N_n
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
            "T-Notes": [1.0] * offset + [3.0] * n_years,
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

        # Default return is in percent: means in [-100, 100], stdev in (0, 100)
        assert np.all(means > -100)
        assert np.all(means < 100)
        assert np.all(stdev > 0)
        assert np.all(stdev < 100)

        assert np.allclose(corr, corr.T)
        assert np.allclose(np.diag(corr), 1.0)
        assert np.all(corr >= -1.0)
        assert np.all(corr <= 1.0)

    def test_get_rates_distributions_with_logger(self):
        """Test getRatesDistributions with custom logger."""
        from owlplanner import mylogging
        mylog = mylogging.Logger(verbose=False)
        frm, to = 2000, 2010
        means, stdev, corr, covar = getRatesDistributions(frm, to, mylog=mylog)
        assert len(means) == 4

    def test_get_rates_distributions_invalid_range(self):
        """Test that getRatesDistributions validates range."""
        with pytest.raises(ValueError, match="out of bounds"):
            getRatesDistributions(1900, 2000)
        with pytest.raises(ValueError, match="out of bounds"):
            getRatesDistributions(2000, 3000)
        with pytest.raises(ValueError, match="must be smaller"):
            getRatesDistributions(2000, 2000)
        with pytest.raises(ValueError, match="must be smaller"):
            getRatesDistributions(2010, 2000)

    def test_get_rates_distributions_different_ranges(self):
        """Test getRatesDistributions with different year ranges."""
        means1, stdev1, corr1, covar1 = getRatesDistributions(2000, 2005)
        means2, stdev2, corr2, covar2 = getRatesDistributions(2000, 2010)

        assert len(means1) == 4
        assert len(means2) == 4
        assert not np.allclose(means1, means2, atol=1e-6)

    def test_get_rates_distributions_correlation_properties(self):
        """Test that correlation matrix has correct properties."""
        frm, to = 2000, 2010
        means, stdev, corr, covar = getRatesDistributions(frm, to)

        assert np.allclose(corr, corr.T)
        assert np.allclose(np.diag(corr), 1.0)
        assert np.all(corr >= -1.0)
        assert np.all(corr <= 1.0)

        assert np.allclose(covar, covar.T)
        # covar is always in decimal; stdev is in percent when in_percent=True
        variances = np.diag(covar)
        expected_variances = (stdev / 100) ** 2
        np.testing.assert_array_almost_equal(variances, expected_variances, decimal=4)

    def test_get_rates_distributions_in_percent_false(self):
        """Test that in_percent=False returns decimal values (backward-compatible)."""
        frm, to = 2000, 2010
        means, stdev, corr, covar = getRatesDistributions(frm, to, in_percent=False)

        # Decimal values: means and stdev should be < 1.0 in magnitude
        assert np.all(np.abs(means) < 1.0)
        assert np.all(stdev < 1.0)
        assert np.all(stdev > 0)

        # Correlation matrix should be unitless regardless
        assert np.allclose(corr, corr.T)
        assert np.allclose(np.diag(corr), 1.0)
        assert np.all(corr >= -1.0)
        assert np.all(corr <= 1.0)

    def test_get_rates_distributions_percent_vs_decimal_consistency(self):
        """Test that in_percent=True values are exactly 100x the in_percent=False values."""
        frm, to = 2000, 2010
        means_pct, stdev_pct, corr_pct, covar_pct = getRatesDistributions(frm, to, in_percent=True)
        means_dec, stdev_dec, corr_dec, covar_dec = getRatesDistributions(frm, to, in_percent=False)

        np.testing.assert_array_almost_equal(means_pct, means_dec * 100, decimal=10)
        np.testing.assert_array_almost_equal(stdev_pct, stdev_dec * 100, decimal=10)
        # corr and covar are never converted; identical across both calls
        np.testing.assert_array_almost_equal(corr_pct, corr_dec, decimal=10)
        np.testing.assert_array_almost_equal(covar_pct, covar_dec, decimal=10)


class TestGetRatesDistributionsDataFrame:
    """Tests for getRatesDistributions with user-supplied DataFrame."""

    def _make_df(self, n=20):
        """Synthetic 4-column DataFrame in percent."""
        rng = np.random.default_rng(0)
        return pd.DataFrame({
            "S&P 500":   rng.normal(7.0, 15.0, n),
            "Bonds Baa": rng.normal(4.5,  8.0, n),
            "T-Notes":   rng.normal(3.5,  5.0, n),
            "Inflation": rng.normal(2.5,  2.0, n),
        })

    def test_df_mode_basic_shapes(self):
        df = self._make_df()
        means, stdev, corr, covar = getRatesDistributions(df=df)
        assert means.shape == (4,)
        assert stdev.shape == (4,)
        assert corr.shape == (4, 4)
        assert covar.shape == (4, 4)

    def test_df_mode_in_percent_true(self):
        df = self._make_df()
        means, stdev, corr, covar = getRatesDistributions(df=df, in_percent=True)
        assert all(abs(means) < 100)     # percent-scale, not decimal

    def test_df_mode_in_percent_false(self):
        df = self._make_df()
        means, stdev, corr, covar = getRatesDistributions(df=df, in_percent=False)
        assert all(abs(means) < 1.0)     # decimal-scale

    def test_df_mode_row_slicing(self):
        df = self._make_df(30)
        means_all, _, _, _ = getRatesDistributions(df=df)
        means_sub, _, _, _ = getRatesDistributions(frm=0, to=9, df=df)  # first 10 rows
        assert not np.allclose(means_all, means_sub)    # different subsets differ

    def test_df_mode_partial_index(self):
        df = self._make_df(20)
        means, stdev, corr, covar = getRatesDistributions(frm=5, df=df)  # frm only
        assert means.shape == (4,)

    def test_df_mode_missing_column(self):
        df = self._make_df().drop(columns=["Inflation"])
        with pytest.raises(ValueError, match="missing required columns"):
            getRatesDistributions(df=df)

    def test_df_mode_too_few_rows(self):
        df = self._make_df(1)
        with pytest.raises(ValueError, match="at least 2 rows"):
            getRatesDistributions(df=df)

    def test_df_mode_correlation_properties(self):
        df = self._make_df(50)
        _, _, corr, _ = getRatesDistributions(df=df)
        assert np.allclose(corr, corr.T)               # symmetric
        assert np.allclose(np.diag(corr), np.ones(4))  # unit diagonal

    def test_historical_mode_still_works(self):
        """Existing positional call signature is unaffected."""
        means, stdev, corr, covar = getRatesDistributions(2000, 2020)
        assert means.shape == (4,)


class TestRatesEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_set_method_multiple_times(self):
        """Test creating models with different methods."""
        m1 = BuiltinRateModel(_model_config("default"))
        s1 = m1.generate(1)
        m2 = BuiltinRateModel(_model_config("optimistic"))
        s2 = m2.generate(1)
        m3 = BuiltinRateModel(_model_config("conservative"))
        s3 = m3.generate(1)
        assert not np.allclose(s1[0], s2[0])
        assert not np.allclose(s2[0], s3[0])

    def test_gen_series_zero_length(self):
        """Test generating series with zero length."""
        m = BuiltinRateModel(_model_config("default"))
        series = m.generate(0)
        assert series.shape == (0, 4)

    def test_gen_series_single_year(self):
        """Test generating series for single year."""
        m = BuiltinRateModel(_model_config("default"))
        series = m.generate(1)
        assert series.shape == (1, 4)

    def test_historical_range_at_boundaries(self):
        """Test historical method at year boundaries."""
        m = BuiltinRateModel(_model_config("historical", frm=FROM, to=FROM + 10))
        series = m.generate(5)
        assert series.shape == (5, 4)

        m2 = BuiltinRateModel(_model_config("historical", frm=TO - 10, to=TO))
        series2 = m2.generate(5)
        assert series2.shape == (5, 4)

    def test_stochastic_with_identity_correlation(self):
        """Test stochastic method with identity correlation (no correlation)."""
        m = BuiltinRateModel(
            _model_config("stochastic", values=[8.0, 5.0, 3.5, 2.5], stdev=[15.0, 8.0, 5.0, 2.0]),
            seed=42,
        )
        series = m.generate(5)
        assert series.shape == (5, 4)
        assert np.allclose(m.params["corr"], np.eye(4))
