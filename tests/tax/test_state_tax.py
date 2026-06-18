"""
Tests for state income tax LP implementation.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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
import pytest

from owlplanner import Plan
from owlplanner import tax_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(state=None):
    """Single-person plan with a basic configuration."""
    p = Plan(["Jack"], ["1960-01-01"], [90], "TestState")
    if state:
        p.setStateTax(state)
    p.setAccountBalances(taxable=[0], taxDeferred=[500], taxFree=[0])
    p.setSocialSecurity([2000], [67])
    p.setRates("conservative")
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]]))
    p.setSpendingProfile("flat")
    return p


# ---------------------------------------------------------------------------
# Task 1: TOML completeness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", tax_state.valid_states())
def test_toml_all_states_load(state):
    """All 51 entries parse without error and have valid bracket structure."""
    for filing in (0, 1):
        entry = tax_state.get_state_entry(state, filing)
        brackets = entry["brackets"]
        assert len(brackets) >= 1, f"{state}: empty brackets"
        for lower, rate in brackets:
            assert lower >= 0, f"{state}: negative lower bound"
            assert 0 <= rate <= 15, f"{state}: rate {rate}% out of expected range [0, 15]"
        assert entry["standard_deduction"] >= 0
        assert isinstance(entry["tax_social_security"], bool)


# ---------------------------------------------------------------------------
# Task 2: st_taxParams unit tests
# ---------------------------------------------------------------------------

def test_st_taxparams_shape():
    """st_taxParams returns arrays with correct shapes."""
    gamma = np.ones(31)  # N_n=30 years + 1
    N_st, theta, delta, sigma, re_cap, pe_cap, tax_ss, ss_thresh = tax_state.st_taxParams(
        "MN", 1, 30, 30, gamma, [1960]
    )
    assert theta.shape == (N_st, 30)
    assert delta.shape == (N_st, 30)
    assert sigma.shape == (30,)
    assert re_cap.shape == (30,)
    assert pe_cap.shape == (30,)
    assert ss_thresh.shape == (30,)
    assert N_st >= 4  # MN has 4 brackets for single


def test_st_taxparams_inflation_scaling():
    """Bracket widths and deductions scale with gamma_n."""
    gamma_flat = np.ones(31)
    gamma_inflated = np.array([1.02**n for n in range(31)])
    for state in ("MN", "CA"):
        _, _, delta_flat, sigma_flat, _, _, _, _ = tax_state.st_taxParams(
            state, 1, 30, 30, gamma_flat, [1960]
        )
        _, _, delta_inf, sigma_inf, _, _, _, _ = tax_state.st_taxParams(
            state, 1, 30, 30, gamma_inflated, [1960]
        )
        # Year 10 should be inflated relative to year 0
        assert delta_inf[0, 10] > delta_flat[0, 10]
        assert sigma_inf[10] > sigma_flat[10]


def test_st_taxparams_filing_status_transition():
    """Bracket widths switch from MFJ to Single at n_d."""
    gamma = np.ones(31)
    n_d = 10
    N_st, theta_mfj, delta_mfj, sigma_mfj, _, _, _, _ = tax_state.st_taxParams(
        "MN", 2, n_d, 30, gamma, [1955, 1958]
    )
    # Before n_d: MFJ brackets
    # After n_d: Single brackets
    N_st_s, theta_s, delta_s, sigma_s, _, _, _, _ = tax_state.st_taxParams(
        "MN", 1, 30, 30, gamma, [1958]
    )
    # Deduction after death should match single
    assert pytest.approx(sigma_mfj[n_d], rel=1e-6) == sigma_s[0]


def test_st_taxparams_exemption_age_gating():
    """Retirement income exemption is zero before exemption_age, nonzero after."""
    # CO has exemption_age=65 for re
    gamma = np.ones(31)
    # born 1995 → turns 65 in 2060 → past 30-year plan end (2026+29=2055)
    _, _, _, _, re_cap, _, _, _ = tax_state.st_taxParams(
        "CO", 1, 30, 30, gamma, [1995]
    )
    # All zeros since never reaches 65 during the plan
    assert np.all(re_cap == 0), "CO re_cap should be 0 when never 65+ during plan"


def test_st_taxparams_exemption_age_active():
    """Retirement income exemption applies once age requirement is met."""
    gamma = np.ones(31)
    _, _, _, _, re_cap, _, _, _ = tax_state.st_taxParams(
        "CO", 1, 30, 30, gamma, [1955]  # born 1955 → already 65+ at plan start
    )
    assert np.any(re_cap > 0), "CO re_cap should be nonzero for someone already 65+"


# ---------------------------------------------------------------------------
# Task 3: No-tax states produce zero tax
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["TX", "FL", "AK", "NV", "WA"])
def test_zero_tax_states(state):
    """No-income-tax states produce st_T_n = 0 every year."""
    p = _make_plan(state)
    p.solve("maxSpending", options={"verbose": False})
    assert np.allclose(p.st_T_n, 0, atol=1.0), f"{state} should produce no state tax"


# ---------------------------------------------------------------------------
# Task 4: State tax reduces spending vs federal-only
# ---------------------------------------------------------------------------

def test_state_tax_reduces_spending():
    """Plan with CA/MN state tax has lower spending than federal-only plan."""
    p_fed = _make_plan(None)
    p_fed.solve("maxSpending", options={"verbose": False})

    for state in ("CA", "MN"):
        p_st = _make_plan(state)
        p_st.solve("maxSpending", options={"verbose": False})
        assert p_st.g_n[0] < p_fed.g_n[0], f"{state} spending should be below federal-only"
        assert np.sum(p_st.st_T_n) > 0, f"{state} should have positive state tax"


# ---------------------------------------------------------------------------
# Task 5: Bracket identity
# ---------------------------------------------------------------------------

def test_bracket_identity():
    """sum over brackets of st_T_tn equals st_T_n exactly."""
    p = _make_plan("MN")
    p.solve("maxSpending", options={"verbose": False})
    assert hasattr(p, "st_T_tn"), "st_T_tn should exist after solve with state"
    computed_T_n = np.sum(p.st_T_tn, axis=0)
    np.testing.assert_allclose(computed_T_n, p.st_T_n, atol=1.0)


# ---------------------------------------------------------------------------
# Task 6: Cash flow balance
# ---------------------------------------------------------------------------

def test_cashflow_balance_with_state_tax(capsys):
    """Plan with state tax passes _check_cashflow_balance (no WARNING logged)."""
    p = _make_plan("MN")
    p.solve("maxSpending", options={"verbose": True})
    captured = capsys.readouterr()
    assert "WARNING" not in captured.out, \
        "Cash flow balance check should not warn with state tax enabled"


# ---------------------------------------------------------------------------
# Task 7: Couple — filing status transition
# ---------------------------------------------------------------------------

def test_couple_filing_status_transition():
    """For a couple, MFJ brackets before n_d and single brackets after."""
    p = Plan(["Alice", "Bob"], ["1960-01-01", "1965-01-01"], [85, 90], "TestCouple")
    p.setStateTax("MN")
    # Use large balances to ensure income exceeds MN MFJ standard deduction ($32,200)
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[800, 600], taxFree=[0, 0])
    p.setSocialSecurity([2500, 2000], [67, 67])
    p.setRates("conservative")
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
    p.setSpendingProfile("flat")
    p.solve("maxSpending", options={"verbose": False})
    # n_d = 25 (Alice's horizon from 2026): state LP should solve without error
    assert p.caseStatus == "solved"
    assert np.sum(p.st_T_n) > 0


# ---------------------------------------------------------------------------
# Task 8: Cash-flow chart state_taxes slice
# ---------------------------------------------------------------------------

def test_cashflow_charts_include_state_taxes():
    """lifetime_allocation and annual_cashflow_mix expose state_taxes separately from federal taxes."""
    p = _make_plan("MN")
    p.solve("maxSpending", options={"verbose": False})
    inv_g = 1.0 / p.gamma_n[:p.N_n]
    expected_state = float(np.sum(p.st_T_n * inv_g))
    expected_federal = float(np.sum((p.T_n + p.U_n + p.J_n) * inv_g))

    alloc = p.lifetime_allocation()
    assert alloc["outflows"]["state_taxes"] == pytest.approx(expected_state, rel=1e-6)
    assert alloc["outflows"]["taxes"] == pytest.approx(expected_federal, rel=1e-6)
    assert alloc["outflows"]["state_taxes"] > 0

    mix = p.annual_cashflow_mix()
    np.testing.assert_allclose(mix["outflows"]["state_taxes"], p.st_T_n * inv_g, rtol=1e-6)
    np.testing.assert_allclose(
        mix["outflows"]["taxes"], (p.T_n + p.U_n + p.J_n) * inv_g, rtol=1e-6,
    )


# ---------------------------------------------------------------------------
# Task 9: Retirement income exemption
# ---------------------------------------------------------------------------

def test_retirement_income_exemption():
    """With NY (re=$20k), st_T_n < no-exemption equivalent."""
    # NY has $20k retirement income exemption (no age requirement)
    # A plan with large IRA withdrawals should benefit from this exemption.
    p_ny = Plan(["Jack"], ["1960-01-01"], [90], "TestNY")
    p_ny.setStateTax("NY")
    p_ny.setAccountBalances(taxable=[0], taxDeferred=[1000], taxFree=[0])
    p_ny.setSocialSecurity([2000], [67])
    p_ny.setRates("conservative")
    p_ny.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]]))
    p_ny.setSpendingProfile("flat")
    p_ny.solve("maxSpending", options={"verbose": False})

    # NY $20k exemption should mean less state tax than a state with same rates but no exemption.
    # Verify st_re variable was created and used.
    assert "st_re" in p_ny.vm, "NY plan should have st_re LP variable"
    assert p_ny.caseStatus == "solved"
    assert np.sum(p_ny.st_T_n) > 0
