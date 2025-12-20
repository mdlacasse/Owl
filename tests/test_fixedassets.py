import pytest
import numpy as np
import pandas as pd

from owlplanner import fixedassets


class TestCalculateFutureValue:
    """Tests for calculate_future_value function."""

    def test_standard_growth(self):
        """Test standard future value calculation."""
        current_value = 100000
        annual_rate = 5.0
        years = 10
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        # FV = 100000 * (1.05)^10 ≈ 162889.46
        expected = 100000 * (1.05 ** 10)
        assert future_value == pytest.approx(expected, abs=1.0)

    def test_zero_growth_rate(self):
        """Test with zero growth rate."""
        current_value = 100000
        annual_rate = 0.0
        years = 10
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        assert future_value == pytest.approx(current_value, abs=0.01)

    def test_zero_years(self):
        """Test with zero years (should return current value)."""
        current_value = 100000
        annual_rate = 5.0
        years = 0
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        assert future_value == pytest.approx(current_value, abs=0.01)

    def test_negative_years(self):
        """Test with negative years (should return current value)."""
        current_value = 100000
        annual_rate = 5.0
        years = -5
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        assert future_value == pytest.approx(current_value, abs=0.01)

    def test_high_growth_rate(self):
        """Test with high growth rate."""
        current_value = 100000
        annual_rate = 10.0
        years = 5
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        expected = 100000 * (1.10 ** 5)
        assert future_value == pytest.approx(expected, abs=1.0)

    def test_fractional_years(self):
        """Test with fractional years."""
        current_value = 100000
        annual_rate = 5.0
        years = 2.5
        future_value = fixedassets.calculate_future_value(current_value, annual_rate, years)
        expected = 100000 * (1.05 ** 2.5)
        assert future_value == pytest.approx(expected, abs=1.0)


class TestGetFixedAssetsArrays:
    """Tests for get_fixed_assets_arrays function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=["name", "type", "basis", "value", "rate", "yod", "commission"])
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
            "basis": 100000,
            "value": 120000,
            "rate": 3.0,
            "yod": 2025,
            "commission": 0.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Gain should be in ordinary income, basis in tax-free
        assert ordinary[0] > 0  # Gain is ordinary income
        assert tax_free[0] == pytest.approx(100000, abs=1.0)  # Basis is tax-free
        assert capital[0] == 0  # No capital gains

    def test_residence_single_small_gain(self):
        """Test primary residence with small gain (within exclusion)."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200000,
            "value": 400000,
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
            "basis": 200000,
            "value": 600000,
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
        assert capital[0] == pytest.approx(120000, abs=1000)  # Taxable portion

    def test_residence_married_large_gain(self):
        """Test primary residence with married filing status."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200000,
            "value": 800000,
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
        assert capital[0] == pytest.approx(60000, abs=1000)

    def test_stocks_with_gain(self):
        """Test stocks asset with capital gain."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100000,
            "value": 150000,
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
        assert tax_free[0] == pytest.approx(100000, abs=1.0)  # Basis is tax-free
        assert ordinary[0] == 0  # No ordinary income

    def test_real_estate_with_gain(self):
        """Test real estate asset with capital gain."""
        df = pd.DataFrame([{
            "name": "rental",
            "type": "real estate",
            "basis": 300000,
            "value": 400000,
            "rate": 3.0,
            "yod": 2025,
            "commission": 6.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(300000, abs=1.0)
        assert ordinary[0] == 0

    def test_collectibles_with_gain(self):
        """Test collectibles asset with capital gain."""
        df = pd.DataFrame([{
            "name": "art",
            "type": "collectibles",
            "basis": 50000,
            "value": 80000,
            "rate": 4.0,
            "yod": 2025,
            "commission": 10.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(50000, abs=1.0)
        assert ordinary[0] == 0

    def test_precious_metals_with_gain(self):
        """Test precious metals asset with capital gain."""
        df = pd.DataFrame([{
            "name": "gold",
            "type": "precious metals",
            "basis": 100000,
            "value": 120000,
            "rate": 2.0,
            "yod": 2025,
            "commission": 2.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(100000, abs=1.0)
        assert ordinary[0] == 0

    def test_asset_with_loss(self):
        """Test asset sold at a loss."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100000,
            "value": 80000,
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
        assert tax_free[0] == pytest.approx(79200, abs=1.0)

    def test_asset_outside_horizon_before(self):
        """Test asset disposed before plan starts."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200000,
            "value": 300000,
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
        """Test asset disposed after plan ends."""
        df = pd.DataFrame([{
            "name": "house",
            "type": "residence",
            "basis": 200000,
            "value": 300000,
            "rate": 2.0,
            "yod": 2040,
            "commission": 5.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Asset disposed in 2040, plan ends in 2034, so should be ignored
        assert np.all(tax_free == 0)
        assert np.all(ordinary == 0)
        assert np.all(capital == 0)

    def test_asset_with_future_growth(self):
        """Test asset that grows before disposition."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "stocks",
            "basis": 100000,
            "value": 100000,  # Current value
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
        assert tax_free[n] == pytest.approx(100000, abs=1.0)

    def test_multiple_assets_same_year(self):
        """Test multiple assets disposed in same year."""
        df = pd.DataFrame([
            {
                "name": "stocks",
                "type": "stocks",
                "basis": 100000,
                "value": 120000,
                "rate": 0.0,
                "yod": 2026,
                "commission": 1.0
            },
            {
                "name": "annuity",
                "type": "fixed annuity",
                "basis": 50000,
                "value": 60000,
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
                "basis": 100000,
                "value": 120000,
                "rate": 0.0,
                "yod": 2026,
                "commission": 1.0
            },
            {
                "name": "house",
                "type": "residence",
                "basis": 200000,
                "value": 300000,
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
            "basis": 100000,
            "value": 120000,
            "rate": 0.0,
            "yod": 2025,
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Should treat as capital gains
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(100000, abs=1.0)
        assert ordinary[0] == 0

    def test_case_insensitive_asset_type(self):
        """Test that asset type is case-insensitive."""
        df = pd.DataFrame([{
            "name": "stocks",
            "type": "STOCKS",  # Uppercase
            "basis": 100000,
            "value": 120000,
            "rate": 0.0,
            "yod": 2025,
            "commission": 1.0
        }])
        thisyear = 2025
        N_n = 10
        tax_free, ordinary, capital = fixedassets.get_fixed_assets_arrays(df, N_n, thisyear)
        # Should work the same as lowercase
        assert capital[0] > 0
        assert tax_free[0] == pytest.approx(100000, abs=1.0)
