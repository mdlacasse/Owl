"""
Tests for from_config / to_config serialization interface on rate models.

Covers:
- Direct unit tests for StochasticRateModel.from_config / to_config
- Direct unit tests for default BaseRateModel.from_config / to_config
- DataFrameRateModel.to_config returning {}
- Full plan → config → plan round-trip for stochastic and bootstrap_sor
- config_to_plan with stochastic TOML keys (exercises the alias-normalization bug fix)

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import numpy as np
import pandas as pd
import pytest

from owlplanner import Plan
from owlplanner.config import config_to_plan, plan_to_config
from owlplanner.rate_models._builtin_impl import _build_corr_matrix
from owlplanner.rate_models.bootstrap_sor import BootstrapSORRateModel
from owlplanner.rate_models.builtin import (
    DefaultRateModel,
    HistoricalAverageRateModel,
    HistoricalRateModel,
    StochasticRateModel,
)
from owlplanner.rate_models.dataframe import DataFrameRateModel


# ---------------------------------------------------------------------------
# Minimal full config dict for config_to_plan tests
# ---------------------------------------------------------------------------

def _minimal_config(rates_section):
    """Return a complete single-person config dict with the supplied rates_selection."""
    return {
        "case_name": "test",
        "description": "",
        "basic_info": {
            "status": "single",
            "names": ["Joe"],
            "date_of_birth": ["1961-01-15"],
            "life_expectancy": [89],
            "start_date": "today",
        },
        "savings_assets": {
            "taxable_savings_balances": [100],
            "tax_deferred_savings_balances": [200],
            "tax_free_savings_balances": [50],
        },
        "household_financial_profile": {"HFP_file_name": "None"},
        "fixed_income": {
            "pension_monthly_amounts": [0],
            "pension_ages": [65],
            "pension_indexed": [True],
            "social_security_pia_amounts": [0],
            "social_security_ages": [67],
        },
        "rates_selection": rates_section,
        "asset_allocation": {
            "interpolation_method": "s-curve",
            "interpolation_center": 15,
            "interpolation_width": 5,
            "type": "individual",
            "generic": [[[60, 40, 0, 0], [70, 30, 0, 0]]],
        },
        "optimization_parameters": {
            "spending_profile": "flat",
            "surviving_spouse_spending_percent": 60,
            "objective": "maxSpending",
        },
        "solver_options": {},
        "results": {"default_plots": "nominal"},
    }


def _base_rates_section(method):
    """Minimal global fields for a rates_selection dict."""
    return {
        "heirs_rate_on_tax_deferred_estate": 30.0,
        "dividend_rate": 1.8,
        "obbba_expiration_year": 2032,
        "method": method,
        "reverse_sequence": False,
        "roll_sequence": 0,
    }


def _make_plan():
    """Minimal configured Plan for round-trip tests."""
    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    return p


# ===========================================================================
# StochasticRateModel.from_config — unit tests
# ===========================================================================

class TestStochasticFromConfig:

    def test_toml_alias_standard_deviations_mapped_to_stdev(self):
        """from_config maps TOML key 'standard_deviations' → internal key 'stdev'."""
        section = {
            "values": [7.0, 4.0, 3.3, 2.8],
            "standard_deviations": [17.0, 8.0, 10.0, 3.0],
        }
        result = StochasticRateModel.from_config(section)
        assert "stdev" in result
        assert "standard_deviations" not in result
        assert result["stdev"] == [17.0, 8.0, 10.0, 3.0]

    def test_toml_alias_correlations_mapped_to_corr(self):
        """from_config maps TOML key 'correlations' → internal key 'corr'."""
        corr_vals = [0.4, 0.26, -0.22, 0.84, -0.39, -0.39]
        section = {
            "values": [7.0, 4.0, 3.3, 2.8],
            "standard_deviations": [17.0, 8.0, 10.0, 3.0],
            "correlations": corr_vals,
        }
        result = StochasticRateModel.from_config(section)
        assert "corr" in result
        assert "correlations" not in result
        assert result["corr"] == corr_vals

    def test_internal_keys_pass_through_unchanged(self):
        """from_config accepts already-internal keys (stdev, corr) without double-mapping."""
        section = {
            "values": [7.0, 4.0, 3.3, 2.8],
            "stdev": [17.0, 8.0, 10.0, 3.0],
            "corr": [0.4, 0.26, -0.22, 0.84, -0.39, -0.39],
        }
        result = StochasticRateModel.from_config(section)
        assert result["stdev"] == [17.0, 8.0, 10.0, 3.0]
        assert result["corr"] == [0.4, 0.26, -0.22, 0.84, -0.39, -0.39]

    def test_non_stochastic_keys_dropped(self):
        """from_config drops keys not declared by StochasticRateModel."""
        section = {
            "values": [7.0, 4.0, 3.3, 2.8],
            "standard_deviations": [17.0, 8.0, 10.0, 3.0],
            "from": 1928,       # historical param — not stochastic
            "to": 2025,         # historical param — not stochastic
            "bogus_key": 99,    # completely unknown
        }
        result = StochasticRateModel.from_config(section)
        assert "from" not in result
        assert "frm" not in result
        assert "to" not in result
        assert "bogus_key" not in result
        assert "values" in result
        assert "stdev" in result

    def test_optional_corr_absent_is_fine(self):
        """from_config works when optional corr / correlations is not provided."""
        section = {
            "values": [7.0, 4.0, 3.3, 2.8],
            "standard_deviations": [17.0, 8.0, 10.0, 3.0],
        }
        result = StochasticRateModel.from_config(section)
        assert "corr" not in result
        assert "correlations" not in result


# ===========================================================================
# StochasticRateModel.to_config — unit tests
# ===========================================================================

class TestStochasticToConfig:

    def test_produces_toml_alias_standard_deviations(self):
        """to_config maps internal 'stdev' → TOML key 'standard_deviations'."""
        result = StochasticRateModel.to_config(
            values=[7.0, 4.0, 3.3, 2.8],
            stdev=[17.0, 8.0, 10.0, 3.0],
            corr=np.eye(4),
        )
        assert "standard_deviations" in result
        assert "stdev" not in result
        assert result["standard_deviations"] == pytest.approx([17.0, 8.0, 10.0, 3.0])

    def test_produces_toml_alias_correlations(self):
        """to_config maps internal 'corr' matrix → TOML key 'correlations'."""
        result = StochasticRateModel.to_config(
            values=[7.0, 4.0, 3.3, 2.8],
            stdev=[17.0, 8.0, 10.0, 3.0],
            corr=np.eye(4),
        )
        assert "correlations" in result
        assert "corr" not in result

    def test_upper_triangle_extracted_correctly(self):
        """to_config extracts the 6 upper-triangle elements from a 4x4 correlation matrix."""
        corr_matrix = np.eye(4)
        corr_matrix[0, 1] = corr_matrix[1, 0] = 0.4
        corr_matrix[0, 2] = corr_matrix[2, 0] = 0.26
        result = StochasticRateModel.to_config(
            values=[7.0, 4.0, 3.3, 2.8],
            stdev=[17.0, 8.0, 10.0, 3.0],
            corr=corr_matrix,
        )
        assert len(result["correlations"]) == 6  # 4*(4-1)//2
        assert result["correlations"][0] == pytest.approx(0.4)   # (0,1)
        assert result["correlations"][1] == pytest.approx(0.26)  # (0,2)
        # Diagonal elements must NOT appear
        assert all(-1.0 <= v <= 1.0 for v in result["correlations"])

    def test_identity_corr_produces_zero_off_diagonals(self):
        """Identity matrix → all 6 upper-triangle correlations are zero."""
        result = StochasticRateModel.to_config(
            values=[7.0, 4.0, 3.3, 2.8],
            stdev=[17.0, 8.0, 10.0, 3.0],
            corr=np.eye(4),
        )
        assert all(v == pytest.approx(0.0) for v in result["correlations"])

    def test_absent_corr_omits_correlations_key(self):
        """to_config omits 'correlations' key when corr is not supplied."""
        result = StochasticRateModel.to_config(
            values=[7.0, 4.0, 3.3, 2.8],
            stdev=[17.0, 8.0, 10.0, 3.0],
        )
        assert "correlations" not in result
        assert "standard_deviations" in result

    def test_alias_round_trip(self):
        """from_config → reconstruct full matrix → to_config preserves alias names and values."""
        section = {
            "values": [7.0, 4.0, 3.3, 2.8],
            "standard_deviations": [17.0, 8.0, 10.0, 3.0],
            "correlations": [0.4, 0.26, -0.22, 0.84, -0.39, -0.39],
        }
        params = StochasticRateModel.from_config(section)
        # Simulate model constructor building the full 4x4 matrix
        params["corr"] = _build_corr_matrix(params["corr"])
        out = StochasticRateModel.to_config(**params)

        assert "standard_deviations" in out
        assert "correlations" in out
        assert out["values"] == pytest.approx([7.0, 4.0, 3.3, 2.8])
        assert out["standard_deviations"] == pytest.approx([17.0, 8.0, 10.0, 3.0])
        assert out["correlations"][0] == pytest.approx(0.4)   # (0,1)
        assert out["correlations"][1] == pytest.approx(0.26)  # (0,2)


# ===========================================================================
# Default BaseRateModel.from_config — unit tests via HistoricalRateModel
# ===========================================================================

class TestDefaultFromConfig:

    def test_from_key_translated_to_frm(self):
        """TOML key 'from' is translated to internal key 'frm'."""
        result = HistoricalRateModel.from_config({"from": 1969, "to": 2000})
        assert "frm" in result
        assert "from" not in result
        assert result["frm"] == 1969

    def test_frm_key_accepted_directly(self):
        """Internal key 'frm' is accepted without translation."""
        result = HistoricalRateModel.from_config({"frm": 1969, "to": 2000})
        assert result["frm"] == 1969

    def test_frm_coerced_to_int(self):
        """'from'/'frm' values are coerced to int."""
        result = HistoricalRateModel.from_config({"from": "1969", "to": "2000"})
        assert isinstance(result["frm"], int)
        assert isinstance(result["to"], int)
        assert result["frm"] == 1969
        assert result["to"] == 2000

    def test_unknown_keys_filtered(self):
        """Keys not in required_parameters | optional_parameters are dropped."""
        result = HistoricalRateModel.from_config({
            "from": 1969,
            "to": 2000,
            "bootstrap_type": "block",   # not a HistoricalRateModel param
            "values": [7, 4, 3, 2],      # not a HistoricalRateModel param
            "bogus": 42,
        })
        assert "bootstrap_type" not in result
        assert "values" not in result
        assert "bogus" not in result
        assert result["frm"] == 1969
        assert result["to"] == 2000

    def test_absent_optional_not_injected(self):
        """Missing optional keys are absent from the result (no injection of None)."""
        # HistoricalRateModel has 'to' as optional with no default
        result = HistoricalRateModel.from_config({"from": 1969})
        assert "to" not in result


# ===========================================================================
# Default BaseRateModel.to_config — unit tests
# ===========================================================================

class TestDefaultToConfig:

    def test_frm_translated_to_from(self):
        """Internal key 'frm' is renamed to TOML key 'from'."""
        result = HistoricalRateModel.to_config(frm=1969, to=2000)
        assert "from" in result
        assert "frm" not in result
        assert result["from"] == 1969
        assert result["to"] == 2000

    def test_computed_fields_filtered_out(self):
        """
        HistoricalAverageRateModel stores computed values/stdev/corr in params
        after generate(); to_config must filter them (only frm/to are declared).
        """
        result = HistoricalAverageRateModel.to_config(
            frm=1969,
            to=2000,
            values=[0.07, 0.04, 0.03, 0.02],   # computed — not declared
            stdev=[0.17, 0.08, 0.06, 0.02],    # computed — not declared
            corr=np.eye(4),                     # computed — not declared
        )
        assert result == {"from": 1969, "to": 2000}

    def test_model_with_no_params_returns_empty(self):
        """DefaultRateModel has no declared parameters; to_config returns {}."""
        assert DefaultRateModel.to_config() == {}

    def test_extra_kwargs_filtered(self):
        """to_config drops kwargs that are not in the model's declared parameters."""
        result = HistoricalRateModel.to_config(frm=1969, to=2000, bogus=99)
        assert "bogus" not in result


# ===========================================================================
# DataFrameRateModel.to_config
# ===========================================================================

class TestDataFrameToConfig:

    def test_returns_empty_dict_always(self):
        """DataFrame cannot be serialized to TOML; to_config must return {}."""
        df = pd.DataFrame({
            "S&P 500": [0.07], "Bonds Baa": [0.04],
            "T-Notes": [0.03], "Inflation": [0.02],
        })
        assert DataFrameRateModel.to_config(df=df, n_years=1, offset=0, in_percent=True) == {}
        assert DataFrameRateModel.to_config() == {}

    def test_plan_to_config_does_not_embed_dataframe(self):
        """Saving a plan with method=dataframe writes no df/n_years keys to config."""
        p = _make_plan()
        n = p.N_n
        df = pd.DataFrame({
            "S&P 500": [5.0] * n, "Bonds Baa": [3.0] * n,
            "T-Notes": [2.5] * n, "Inflation": [2.0] * n,
        })
        p.setRates(method="dataframe", df=df)
        diconf = plan_to_config(p)
        rates = diconf["rates_selection"]

        assert "df" not in rates
        assert "n_years" not in rates
        # from/to defaults must still be present (UI bridge expects them)
        assert "from" in rates
        assert "to" in rates


# ===========================================================================
# Stochastic config → plan via config_to_plan (the alias-normalization bug fix)
# ===========================================================================

class TestStochasticConfigToPlan:

    def test_loads_standard_deviations_and_correlations_from_toml_keys(self):
        """
        config_to_plan correctly processes standard_deviations/correlations from
        a rates_selection dict.  This exercises StochasticRateModel.from_config's
        alias-normalization — the path that was silently broken before the fix.
        """
        rates = _base_rates_section("stochastic")
        rates.update({
            "values": [7.0, 4.0, 3.3, 2.8],
            "standard_deviations": [17.0, 8.0, 10.0, 3.0],
            "correlations": [0.4, 0.26, -0.22, 0.84, -0.39, -0.39],
            "from": 1928,
            "to": 2025,
        })
        plan = config_to_plan(_minimal_config(rates), verbose=False, loadHFP=False)

        assert plan.rateMethod == "stochastic"
        assert plan.tau_kn.shape == (4, plan.N_n)
        assert plan.rateValues == pytest.approx([7.0, 4.0, 3.3, 2.8])
        assert plan.rateStdev == pytest.approx([17.0, 8.0, 10.0, 3.0])
        assert plan.rateCorr is not None
        assert plan.rateCorr[0, 1] == pytest.approx(0.4)

    def test_loads_without_correlations(self):
        """Stochastic config without correlations key loads and uses identity matrix."""
        rates = _base_rates_section("stochastic")
        rates.update({
            "values": [7.0, 4.0, 3.3, 2.8],
            "standard_deviations": [17.0, 8.0, 10.0, 3.0],
            "from": 1928,
            "to": 2025,
        })
        plan = config_to_plan(_minimal_config(rates), verbose=False, loadHFP=False)

        assert plan.rateMethod == "stochastic"
        assert plan.tau_kn.shape == (4, plan.N_n)
        assert np.allclose(plan.rateCorr, np.eye(4))


# ===========================================================================
# Stochastic full round-trip: plan → config → plan
# ===========================================================================

class TestStochasticRoundTrip:

    def test_values_and_stdev_preserved(self):
        """plan → config → plan preserves rateValues and rateStdev."""
        p = _make_plan()
        p.setRates("stochastic", values=[7.0, 4.0, 3.3, 2.8], stdev=[17.0, 8.0, 10.0, 3.0])

        diconf = plan_to_config(p)
        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)

        assert p2.rateMethod == "stochastic"
        assert p2.rateValues == pytest.approx([7.0, 4.0, 3.3, 2.8])
        assert p2.rateStdev == pytest.approx([17.0, 8.0, 10.0, 3.0])

    def test_config_contains_toml_names(self):
        """plan_to_config writes 'standard_deviations' and 'correlations' (not stdev/corr)."""
        p = _make_plan()
        p.setRates("stochastic", values=[7.0, 4.0, 3.3, 2.8], stdev=[17.0, 8.0, 10.0, 3.0])

        diconf = plan_to_config(p)
        rates = diconf["rates_selection"]

        assert "standard_deviations" in rates
        assert "correlations" in rates
        assert "stdev" not in rates
        assert "corr" not in rates

    def test_correlation_matrix_preserved(self):
        """plan → config → plan preserves the full correlation matrix (not just diagonal)."""
        p = _make_plan()
        corr_upper = [0.4, 0.26, -0.22, 0.84, -0.39, -0.39]
        p.setRates(
            "stochastic",
            values=[7.0, 4.0, 3.3, 2.8],
            stdev=[17.0, 8.0, 10.0, 3.0],
            corr=corr_upper,
        )

        diconf = plan_to_config(p)
        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)

        assert np.allclose(p.rateCorr, p2.rateCorr, atol=1e-9)

    def test_identity_corr_round_trip(self):
        """plan with no explicit corr (identity) round-trips cleanly."""
        p = _make_plan()
        p.setRates("stochastic", values=[7.0, 4.0, 3.3, 2.8], stdev=[17.0, 8.0, 10.0, 3.0])

        diconf = plan_to_config(p)
        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)

        assert np.allclose(p2.rateCorr, np.eye(4))


# ===========================================================================
# BootstrapSORRateModel — unit tests + round-trip
# ===========================================================================

class TestBootstrapSORSerialization:

    def test_from_config_translates_from_to_frm(self):
        """from_config translates 'from' → 'frm' for bootstrap_sor."""
        section = {
            "from": 1969,
            "to": 2024,
            "bootstrap_type": "block",
            "block_size": 5,
            "crisis_years": [1973, 2008],
            "crisis_weight": 2.0,
        }
        result = BootstrapSORRateModel.from_config(section)
        assert "frm" in result
        assert "from" not in result
        assert result["frm"] == 1969
        assert result["to"] == 2024
        assert result["bootstrap_type"] == "block"
        assert result["block_size"] == 5
        assert result["crisis_years"] == [1973, 2008]
        assert result["crisis_weight"] == 2.0

    def test_from_config_drops_non_bootstrap_keys(self):
        """from_config drops keys not declared by BootstrapSORRateModel."""
        section = {
            "from": 1969, "to": 2024,
            "values": [7, 4, 3, 2],          # stochastic param — not bootstrap
            "standard_deviations": [17, 8, 6, 2],
        }
        result = BootstrapSORRateModel.from_config(section)
        assert "values" not in result
        assert "standard_deviations" not in result
        assert result["frm"] == 1969

    def test_to_config_translates_frm_to_from(self):
        """to_config translates 'frm' → 'from' and includes all declared optional params."""
        result = BootstrapSORRateModel.to_config(
            frm=1969, to=2024,
            bootstrap_type="block", block_size=5,
            crisis_years=[1973, 2008], crisis_weight=2.0,
        )
        assert "from" in result
        assert "frm" not in result
        assert result["from"] == 1969
        assert result["bootstrap_type"] == "block"
        assert result["block_size"] == 5

    def test_to_config_omits_undeclared_extras(self):
        """to_config drops kwargs not in required_parameters | optional_parameters."""
        result = BootstrapSORRateModel.to_config(frm=1969, to=2024, bogus=42)
        assert "bogus" not in result
        assert result["from"] == 1969

    def test_full_round_trip(self):
        """plan.setRates(bootstrap_sor) → plan_to_config → config_to_plan preserves params."""
        p = _make_plan()
        p.setRates(
            method="bootstrap_sor",
            frm=1950,
            to=2020,
            bootstrap_type="block",
            block_size=5,
        )

        diconf = plan_to_config(p)
        rates = diconf["rates_selection"]

        assert rates["method"] == "bootstrap_sor"
        assert rates["from"] == 1950
        assert rates["to"] == 2020
        assert rates["bootstrap_type"] == "block"
        assert rates["block_size"] == 5

        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)
        assert p2.rateMethod == "bootstrap_sor"
        assert p2.rateFrm == 1950
        assert p2.rateTo == 2020
        assert p2.tau_kn.shape == (4, p2.N_n)

    def test_round_trip_preserves_optional_defaults(self):
        """Optional params with defaults survive a round-trip even when not explicitly set."""
        p = _make_plan()
        p.setRates(method="bootstrap_sor", frm=1950, to=2020)  # no optional params

        diconf = plan_to_config(p)
        rates = diconf["rates_selection"]

        # Defaults must be serialized so they round-trip
        assert "bootstrap_type" in rates
        assert "block_size" in rates

        p2 = config_to_plan(diconf, verbose=False, loadHFP=False)
        assert p2.rateMethod == "bootstrap_sor"
        assert p2.tau_kn.shape == (4, p2.N_n)
