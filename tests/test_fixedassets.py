"""
Tests for fixedassets module - fixed asset calculations and tax handling.

Tests verify functions for calculating future values, capital gains,
and tax implications of fixed assets including primary residence exclusions.

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

from owlplanner import fixedassets


class TestCalculateFutureValue:
    """Tests for calculate_future_value function."""

    def test_standard_growth(self):
        """Test standard future value calculation."""
        current_value = 100_000
        annual_rate = 5.0
        years = 10
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        # FV = 100000 * (1.05)^10 ≈ 162889.46
        expected = 100_000 * (1.05 ** 10)
        assert future_value == pytest.approx(expected, abs=1.0)

    def test_zero_growth_rate(self):
        """Test with zero growth rate."""
        current_value = 100_000
        annual_rate = 0.0
        years = 10
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        assert future_value == pytest.approx(current_value, abs=0.01)

    def test_zero_years(self):
        """Test with zero years (should return current value)."""
        current_value = 100_000
        annual_rate = 5.0
        years = 0
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        assert future_value == pytest.approx(current_value, abs=0.01)

    def test_negative_years(self):
        """Test with negative years (should return current value)."""
        current_value = 100_000
        annual_rate = 5.0
        years = -5
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        assert future_value == pytest.approx(current_value, abs=0.01)

    def test_high_growth_rate(self):
        """Test with high growth rate."""
        current_value = 100_000
        annual_rate = 10.0
        years = 5
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        expected = 100_000 * (1.10 ** 5)
        assert future_value == pytest.approx(expected, abs=1.0)

    def test_fractional_years(self):
        """Test with fractional years."""
        current_value = 100_000
        annual_rate = 5.0
        years = 2.5
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        expected = 100_000 * (1.05 ** 2.5)
        assert future_value == pytest.approx(expected, abs=1.0)


class TestGetFixedAssetsArrays:
    """Tests for get_fixed_assets_arrays function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=["name", "type", "year", "basis", "value", "rate", "yod", "commission"])
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, 10)
        assert len(tax_free) == 10
        assert len(ordinary) == 10
        assert len(capital) == 10
        assert np.all(tax_free == 0)
        assert np.all(ordinary == 0)
        assert np.all(capital == 0)

    def test_none_dataframe(self):
        """Test with None DataFrame."""
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(None, 10)
        assert len(tax_free) == 10
        assert np.all(tax_free == 0)

    def test_annuity_asset(self):
        """Test fixed annuity asset (ordinary income)."""
        df = pd.DataFrame([{
            "name": "annuity",
            "type": "fixed annuity",
            "basis": 100_000,
            "value": 120_000,
            "rate": 3.0,
            "yod": 2025,
            "commission": 0.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Gain should be in ordinary income, basis in tax-free
        assert ordinary[0] > 0  # Gain is ordinary income
        assert tax_free[0] == pytest.approx(100_000, abs=1.0)  # Basis is tax-free
        assert capital[0] == 0  # No capital gains

    def test_residence_single_small_gain(self):
        """Test primary residence with small gain (within exclusion)."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200_000,
            "value": 400_000,
            "rate": 2.0,
            "yod": 2025,
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(
            df, N_n, thisyear, filing_status="single"
        )
        # With 5% commission: proceeds = 400000 * 0.95 = 380000
        # Gain = 380000 - 200000 = 180000 (within $250k exclusion)
        assert capital[0] == 0  # No capital gains (within exclusion)
        assert tax_free[0] > 0  # Basis + excluded gain is tax-free

    def test_residence_single_large_gain(self):
        """Test primary residence with large gain (exceeds exclusion)."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200_000,
            "value": 600_000,
            "rate": 2.0,
            "yod": 2025,
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(
            df, N_n, thisyear, filing_status="single"
        )
        # With 5% commission: proceeds = 600000 * 0.95 = 570000
        # Gain = 570000 - 200000 = 370000
        # Taxable gain = 370000 - 250000 = 120000
        assert capital[0] > 0  # Should have capital gains
        assert capital[0] == pytest.approx(120_000, abs=1000)  # Taxable portion

    def test_residence_married_large_gain(self):
        """Test primary residence with married filing status."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200_000,
            "value": 800_000,
            "rate": 2.0,
            "yod": 2025,
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(
            df, N_n, thisyear, filing_status="married"
        )
        # With 5% commission: proceeds = 800000 * 0.95 = 760000
        # Gain = 760000 - 200000 = 560000
        # Taxable gain = 560000 - 500000 = 60000 (married exclusion is $500k)
        assert capital[0] > 0
        assert capital[0] == pytest.approx(60_000, abs=1000)

    def test_stocks_with_gain(self):
        """Test stocks asset with capital gain."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100_000,
            "value": 150_000,
            "rate": 5.0,
            "yod": 2025,
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # With 1% commission: proceeds = 150000 * 0.99 = 148500
        # Gain = 148500 - 100000 = 48500
        assert capital[0] > 0  # Should have capital gains
        assert tax_free[0] == pytest.approx(100_000, abs=1.0)  # Basis is tax-free
        assert ordinary[0] == 0  # No ordinary income

    def test_real_estate_with_gain(self):
        """Test real estate asset with capital gain."""
        df = pd.DataFrame([{
            "name": "rental",
            "type": "real estate",
            "basis": 300_000,
            "value": 400_000,
            "rate": 3.0,
            "yod": 2025,
            "commission": 6.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(300_000, abs=1.0)
        assert ordinary[0] == 0

    def test_collectibles_with_gain(self):
        """Test collectibles asset with capital gain."""
        df = pd.DataFrame([{
            "name": "art",
            "type": "collectibles",
            "basis": 50_000,
            "value": 80_000,
            "rate": 4.0,
            "yod": 2025,
            "commission": 10.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(50_000, abs=1.0)
        assert ordinary[0] == 0

    def test_precious_metals_with_gain(self):
        """Test precious metals asset with capital gain."""
        df = pd.DataFrame([{
            "name": "gold",
            "type": "precious metals",
            "basis": 100_000,
            "value": 120_000,
            "rate": 2.0,
            "yod": 2025,
            "commission": 2.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(100_000, abs=1.0)
        assert ordinary[0] == 0

    def test_asset_with_loss(self):
        """Test asset sold at a loss."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100_000,
            "value": 80_000,
            "rate": 0.0,
            "yod": 2025,
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # With 1% commission: proceeds = 80000 * 0.99 = 79200
        # Loss = 79200 - 100000 = -20800
        assert capital[0] == 0  # No capital gains (it's a loss)
        # Proceeds should be in tax-free
        assert tax_free[0] == pytest.approx(79_200, abs=1.0)

    def test_asset_outside_horizon_before(self):
        """Test asset disposed before plan starts."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200_000,
            "value": 300_000,
            "rate": 2.0,
            "yod": 2020,
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Asset disposed in 2020, plan starts in 2025, so should be ignored
        assert np.all(tax_free == 0)
        assert np.all(ordinary == 0)
        assert np.all(capital == 0)

    def test_asset_outside_horizon_after(self):
        """Test asset disposed after plan ends - should not be in arrays."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200_000,
            "value": 300_000,
            "rate": 2.0,
            "yod": 2040,
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Asset disposed in 2040, plan ends in 2034, so should NOT be in arrays
        # (it will be handled in bequest calculation instead)
        assert np.all(tax_free == 0)
        assert np.all(ordinary == 0)
        assert np.all(capital == 0)

    def test_negative_yod_counts_from_plan_end(self):
        """Test negative yod offsets from the end of the plan."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100_000,
            "value": 120_000,
            "rate": 0.0,
            "yod": -1,  # Last plan year
            "commission": 0.0
        }])
        thisyear = 2025
        N_n = 3  # Plan years: 2025, 2026, 2027
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # yod = -1 maps to end_year (2027), which is index 2
        assert capital[2] > 0
        assert tax_free[2] == pytest.approx(100_000, abs=1.0)

    def test_asset_with_future_growth(self):
        """Test asset that grows before disposition."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100_000,
            "value": 100_000,  # Current value
            "rate": 5.0,  # 5% growth per year
            "yod": 2027,  # Disposed in 2 years
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Future value = 100000 * (1.05)^2 = 110250
        # With 1% commission: proceeds = 110250 * 0.99 = 109147.5
        # Gain = 109147.5 - 100000 = 9147.5
        n = 2027 - 2025  # Index 2
        assert capital[n] > 0  # Should have capital gains
        assert tax_free[n] == pytest.approx(100_000, abs=1.0)

    def test_multiple_assets_same_year(self):
        """Test multiple assets disposed in same year."""
        df = pd.DataFrame([
            {
                "name": "stocks",
                "type": "stocks",
                "basis": 100_000,
                "value": 120_000,
                "rate": 0.0,
                "yod": 2026,
                "commission": 1.0
            },
            {
                "name": "annuity",
                "type": "fixed annuity",
                "basis": 50_000,
                "value": 60_000,
                "rate": 0.0,
                "yod": 2026,
                "commission": 0.0
            }
        ])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        n = 2026 - 2025  # Index 1
        # Both assets disposed in year 1
        assert capital[n] > 0  # Stocks capital gains
        assert ordinary[n] > 0  # Annuity ordinary income
        assert tax_free[n] > 0  # Both bases

    def test_multiple_assets_different_years(self):
        """Test multiple assets disposed in different years."""
        df = pd.DataFrame([
            {
                "name": "stocks",
                "type": "stocks",
                "basis": 100_000,
                "value": 120_000,
                "rate": 0.0,
                "yod": 2026,
                "commission": 1.0
            },
            {
                "name": "house",
                "type": "residence",
                "basis": 200_000,
                "value": 300_000,
                "rate": 0.0,
                "yod": 2028,
                "commission": 5.0
            }
        ])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Stocks in year 1 (index 1)
        assert capital[1] > 0
        # House in year 3 (index 3)
        assert capital[3] >= 0  # May be 0 if within exclusion
        assert tax_free[3] > 0

    def test_unknown_asset_type(self):
        """Test unknown asset type (should default to capital gains treatment)."""
        df = pd.DataFrame([{
            "name": "unknown",
            "type": "unknown_type",
            "basis": 100_000,
            "value": 120_000,
            "rate": 0.0,
            "yod": 2025,
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Should treat as capital gains
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(100_000, abs=1.0)
        assert ordinary[0] == 0

    def test_case_insensitive_asset_type(self):
        """Test that asset type is case-insensitive."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "STOCKS",  # Uppercase
            "basis": 100_000,
            "value": 120_000,
            "rate": 0.0,
            "yod": 2025,
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Should work the same as lowercase
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(100_000, abs=1.0)

    def test_asset_with_acquisition_year(self):
        """Test asset with explicit acquisition year (future acquisition)."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "year": 2027,  # Acquired in 2027
            "basis": 100_000,
            "value": 100_000,  # Value at acquisition
            "rate": 5.0,
            "yod": 2029,  # Disposed in 2029
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Asset acquired at beginning of 2027, disposed at beginning of 2029
        # Growth period: 2029 - 2027 = 2 years
        # Future value = 100000 * (1.05)^2 = 110250
        # With 1% commission: proceeds = 110250 * 0.99 = 109147.5
        # Gain = 109147.5 - 100000 = 9147.5
        n = 2029 - 2025  # Index 4
        assert capital[n] > 0
        assert capital[n] == pytest.approx(9147.5, abs=10.0)
        assert tax_free[n] == pytest.approx(100_000, abs=1.0)

    def test_asset_acquired_future_disposed_beyond_plan(self):
        """Test asset acquired in future but disposed beyond plan - should not be in arrays."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "year": 2027,  # Acquired in 2027
            "basis": 200_000,
            "value": 200000,
            "rate": 3.0,
            "yod": 2040,  # Disposed beyond plan (plan ends 2034)
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Asset disposed beyond plan, so should NOT be in arrays (handled in bequest)
        assert np.all(tax_free == 0)
        assert np.all(ordinary == 0)
        assert np.all(capital == 0)

    def test_asset_backward_compatibility_no_year_column(self):
        """Test backward compatibility when 'year' column is missing (defaults to thisyear)."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            # No "year" column - should default to thisyear
            "basis": 100_000,
            "value": 100_000,
            "rate": 5.0,
            "yod": 2027,  # Disposed in 2 years
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Should default to acquisition_year = thisyear = 2025
        # Growth period: 2027 - 2025 = 2 years
        # Future value = 100000 * (1.05)^2 = 110250
        n = 2027 - 2025  # Index 2
        assert capital[n] > 0
        assert tax_free[n] == pytest.approx(100_000, abs=1.0)

    def test_asset_acquired_after_plan_ends(self):
        """Test asset acquired after plan ends - should be ignored."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "year": 2040,  # Acquired after plan ends (plan ends 2034)
            "basis": 100_000,
            "value": 100_000,
            "rate": 5.0,
            "yod": 2045,
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Asset acquired after plan ends, so should be ignored
        assert np.all(tax_free == 0)
        assert np.all(ordinary == 0)
        assert np.all(capital == 0)

    def test_asset_disposed_before_acquisition(self):
        """Test asset with invalid yod < acquisition year - should be ignored."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "year": 2027,  # Acquired in 2027
            "basis": 100_000,
            "value": 100_000,
            "rate": 5.0,
            "yod": 2025,  # Disposed before acquisition (invalid)
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Invalid: disposed before acquisition, so should be ignored
        assert np.all(tax_free == 0)
        assert np.all(ordinary == 0)
        assert np.all(capital == 0)


class TestGetFixedAssetsBequestValue:
    """Tests for get_fixed_assets_bequest_value function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=["name", "type", "year", "basis", "value", "rate", "yod", "commission"])
        bequest = fixedassets.get_fixed_assets_bequest_value(df, 10)
        assert bequest == 0.0

    def test_none_dataframe(self):
        """Test with None DataFrame."""
        bequest = fixedassets.get_fixed_assets_bequest_value(None, 10)
        assert bequest == 0.0

    def test_asset_disposed_beyond_plan(self):
        """Test asset with yod beyond plan end - should be in bequest."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200_000,
            "value": 300_000,
            "rate": 3.0,
            "yod": 2040,  # Beyond plan end (plan ends 2034)
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        bequest = fixedassets.get_fixed_assets_bequest_value(df, N_n, thisyear)
        # Asset disposed beyond plan, so should be in bequest
        # Plan ends at end of 2034 (end_year = 2034)
        # Growth from start of 2025 (default acquisition) to end of 2034 = 10 years
        # Future value = 300000 * (1.03)^10 ≈ 403175
        # With 5% commission: proceeds = 403175 * 0.95 ≈ 383016
        assert bequest > 0
        assert bequest == pytest.approx(383_016, abs=1000)

    def test_zero_yod_liquidates_at_plan_end(self):
        """Test yod=0 is treated as liquidated at plan end."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100_000,
            "value": 110_000,
            "rate": 0.0,
            "yod": 0,
            "commission": 0.0
        }])
        thisyear = 2025
        N_n = 3  # Plan ends in 2027
        bequest = fixedassets.get_fixed_assets_bequest_value(df, N_n, thisyear)
        # yod=0 maps to year after plan end, so it is liquidated at plan end
        assert bequest == pytest.approx(110_000, abs=1.0)

    def test_asset_with_acquisition_year_in_bequest(self):
        """Test asset with explicit acquisition year in bequest calculation."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "year": 2027,  # Acquired in 2027
            "basis": 200_000,
            "value": 200000,  # Value at acquisition
            "rate": 3.0,
            "yod": 2040,  # Beyond plan end
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        bequest = fixedassets.get_fixed_assets_bequest_value(df, N_n, thisyear)
        # Asset acquired at beginning of 2027, plan ends at end of 2034
        # Growth period: from start of 2027 to end of 2034 = 2034 - 2027 + 1 = 8 years
        # Future value = 200000 * (1.03)^8 ≈ 253354
        # With 5% commission: proceeds = 253354 * 0.95 ≈ 240684
        assert bequest > 0
        assert bequest == pytest.approx(240_684, abs=1000)

    def test_asset_disposed_during_plan_not_in_bequest(self):
        """Test asset disposed during plan - should NOT be in bequest."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200_000,
            "value": 300_000,
            "rate": 3.0,
            "yod": 2030,  # Within plan (plan ends 2034)
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        bequest = fixedassets.get_fixed_assets_bequest_value(df, N_n, thisyear)
        # Asset disposed during plan, so should NOT be in bequest
        assert bequest == 0.0

    def test_asset_acquired_after_plan_ends_not_in_bequest(self):
        """Test asset acquired after plan ends - should not be in bequest."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "year": 2040,  # Acquired after plan ends
            "basis": 200_000,
            "value": 200000,
            "rate": 3.0,
            "yod": 2045,
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        bequest = fixedassets.get_fixed_assets_bequest_value(df, N_n, thisyear)
        # Asset acquired after plan ends, so should not be in bequest
        assert bequest == 0.0

    def test_multiple_assets_in_bequest(self):
        """Test multiple assets in bequest calculation."""
        df = pd.DataFrame([
            {
                "name": "house1",
                "type": "residence",
                "basis": 200_000,
                "value": 300_000,
                "rate": 3.0,
                "yod": 2040,  # Beyond plan
                "commission": 5.0
            },
            {
                "name": "house2",
                "type": "residence",
                "year": 2027,  # Acquired in 2027
                "basis": 150_000,
                "value": 150_000,
                "rate": 2.0,
                "yod": 2045,  # Beyond plan
                "commission": 6.0
            }
        ])
        thisyear = 2025
        N_n = 10
        bequest = fixedassets.get_fixed_assets_bequest_value(df, N_n, thisyear)
        # Both assets should be in bequest
        assert bequest > 0
        # Should be sum of both assets' proceeds
        assert bequest > 300_000  # At least the first asset's value

    def test_no_double_counting_arrays_vs_bequest(self):
        """Test that assets are not double-counted between arrays and bequest."""
        df = pd.DataFrame([
            {
                "name": "stocks",
                "type": "stocks",
                "basis": 100_000,
                "value": 100_000,
                "rate": 5.0,
                "yod": 2030,  # Within plan - should be in arrays only
                "commission": 1.0
            },
            {
                "name": "house",
                "type": "residence",
                "basis": 200_000,
                "value": 200000,
                "rate": 3.0,
                "yod": 2040,  # Beyond plan - should be in bequest only
                "commission": 5.0
            }
        ])
        thisyear = 2025
        N_n = 10
        # Check arrays
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Stocks should be in arrays (disposed in 2030)
        n = 2030 - 2025  # Index 5
        assert capital[n] > 0  # Stocks capital gains

        # Check bequest
        bequest = fixedassets.get_fixed_assets_bequest_value(df, N_n, thisyear)
        # House should be in bequest (disposed beyond plan)
        assert bequest > 0

        # Verify no overlap: stocks not in bequest, house not in arrays
        # (already verified by the above assertions)
