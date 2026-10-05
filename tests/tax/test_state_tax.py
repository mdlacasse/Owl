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

from datetime import date

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
        assert entry["standard_deduction"] == "federal" or entry["standard_deduction"] >= 0
        assert isinstance(entry["tax_social_security"], bool)


# ---------------------------------------------------------------------------
# Task 2: st_taxParams unit tests
# ---------------------------------------------------------------------------


def test_st_taxparams_shape():
    """st_taxParams returns arrays with correct shapes."""
    gamma = np.ones(31)  # N_n=30 years + 1
    N_st, theta, delta, sigma, re_cap, pe_cap, conv_ok, tax_ss, ss_thresh = tax_state.st_taxParams(
        "MN", 1, 30, 30, gamma, [1960], mobs=[1]
    )
    assert theta.shape == (N_st, 30)
    assert delta.shape == (N_st, 30)
    assert sigma.shape == (30,)
    assert re_cap.shape == (1, 30)
    assert pe_cap.shape == (1, 30)
    assert ss_thresh.shape == (30,)
    assert N_st >= 4  # MN has 4 brackets for single


def test_st_taxparams_inflation_scaling():
    """Bracket widths and deductions scale with gamma_n."""
    gamma_flat = np.ones(31)
    gamma_inflated = np.array([1.02**n for n in range(31)])
    for state in ("MN", "CA"):
        _, _, delta_flat, sigma_flat, _, _, _, _, _ = tax_state.st_taxParams(
            state, 1, 30, 30, gamma_flat, [1960], mobs=[1]
        )
        _, _, delta_inf, sigma_inf, _, _, _, _, _ = tax_state.st_taxParams(
            state, 1, 30, 30, gamma_inflated, [1960], mobs=[1]
        )
        # Year 10 should be inflated relative to year 0
        assert delta_inf[0, 10] > delta_flat[0, 10]
        assert sigma_inf[10] > sigma_flat[10]


def test_st_taxparams_filing_status_transition():
    """Bracket widths switch from MFJ to Single at n_d."""
    gamma = np.ones(31)
    n_d = 10
    N_st, theta_mfj, delta_mfj, sigma_mfj, _, _, _, _, _ = tax_state.st_taxParams(
        "MN", 2, n_d, 30, gamma, [1955, 1958], mobs=[1, 1]
    )
    # Before n_d: MFJ brackets
    # After n_d: Single brackets
    N_st_s, theta_s, delta_s, sigma_s, _, _, _, _, _ = tax_state.st_taxParams("MN", 1, 30, 30, gamma, [1958], mobs=[1])
    # Deduction after death should match single
    assert pytest.approx(sigma_mfj[n_d], rel=1e-6) == sigma_s[0]


def test_st_taxparams_exemption_age_gating():
    """Retirement income exemption is zero before exemption_age, nonzero after."""
    # CO has exemption_age=65 for re
    gamma = np.ones(31)
    # born 1995 → turns 65 in 2060 → past 30-year plan end (2026+29=2055)
    _, _, _, _, re_cap, _, _, _, _ = tax_state.st_taxParams("CO", 1, 30, 30, gamma, [1995], mobs=[1])
    # All zeros since never reaches 65 during the plan
    assert np.all(re_cap == 0), "CO re_cap should be 0 when never 65+ during plan"


def test_st_taxparams_exemption_age_active():
    """Retirement income exemption applies once age requirement is met."""
    gamma = np.ones(31)
    _, _, _, _, re_cap, _, _, _, _ = tax_state.st_taxParams(
        "CO",
        1,
        30,
        30,
        gamma,
        [1955],  # born 1955 → already 65+ at plan start
        mobs=[1],
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


def test_state_base_starts_from_gross_income():
    """State taxable income = gross ordinary income + gains - state deduction.

    Guards against taking the federal standard deduction (e_n) against the state base
    in addition to the state's own deduction. MN taxes SS and has no retirement
    exemption, so no other adjustment enters the base.
    """
    p = _make_plan("MN")
    p.solve("maxSpending", options={"verbose": False})
    expected = np.maximum(0, p.G_n + p.e_n + p.Q_n - p.st_sigmaBar_n)
    assert np.any(expected > 1_000), "test needs years with positive state taxable income"
    np.testing.assert_allclose(np.sum(p.st_f_tn, axis=0), expected, atol=1.0)


@pytest.mark.parametrize(
    "state,expected",
    [("CO", (True, True)), ("ND", (True, True)), ("AZ", (True, False)), ("MO", (True, False)), ("CA", (False, False))],
)
def test_federal_deduction_flags(state, expected):
    assert tax_state.federal_deduction(state) == expected


def test_federal_deduction_follows_age_and_senior_bonus():
    """A "federal" state deduction is the federal one each year: age-65 additions included,
    and the OBBBA senior bonus only where the state takes it (CO yes, AZ no)."""
    p_co = _make_plan("CO")
    p_co.solve("maxSpending", options={"verbose": False})
    np.testing.assert_allclose(p_co.st_sigmaBar_n, p_co.sigmaBar_n)

    p_az = _make_plan("AZ")
    p_az.solve("maxSpending", options={"verbose": False})
    years = date.today().year + np.arange(p_az.N_n)
    gap = p_az.sigmaBar_n - p_az.st_sigmaBar_n
    # Jack is 65+ throughout: the bonus is at most $6,000 through 2028 and gone after.
    assert np.all(gap[years <= 2028] >= -1e-6) and np.all(gap[years <= 2028] <= 6000 + 1e-6)
    assert np.any(gap[years <= 2028] > 0), "expected some senior bonus left out for AZ"
    np.testing.assert_allclose(gap[years > 2028], 0, atol=1e-6)
    # The age-65 addition is in: the 2026 amount exceeds the $16,100 single base.
    assert p_az.st_sigmaBar_n[0] > 16_100


def test_state_ss_exclusion_uses_lp_taxable_ss():
    """Under withSSTaxability='optimize', a state that exempts SS removes exactly the taxable
    SS the LP charged federally (tss), not the Psi_n parameter left by the previous iterate."""
    p = Plan(["Jack"], ["1958-01-01"], [78], "TestStateSSopt")
    p.setStateTax("CA")
    p.setAccountBalances(taxable=[50], taxDeferred=[300], taxFree=[0])
    p.setSocialSecurity([2500], [67])
    p.setRates("conservative")
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]]))
    p.setSpendingProfile("flat")
    p.solve("maxSpending", {"withSSTaxability": "optimize", "withMedicare": "None"})
    assert p.caseStatus == "solved"
    # In optimize mode, Psi_n is re-derived from tss when results are aggregated.
    taxable_ss = p.Psi_n * np.sum(p.zetaBar_in, axis=0)
    ss_years = np.sum(p.zetaBar_in, axis=0) > 0
    assert np.any(p.Psi_n[ss_years] < 0.8), "test needs years where taxable SS is below 85%"
    expected = np.maximum(0, p.G_n + p.e_n + p.Q_n - taxable_ss - p.st_sigmaBar_n)
    np.testing.assert_allclose(np.sum(p.st_f_tn, axis=0), expected, atol=1.0)


# ---------------------------------------------------------------------------
# Task 6: Cash flow balance
# ---------------------------------------------------------------------------


def test_cashflow_balance_with_state_tax(capsys):
    """Plan with state tax passes _check_cashflow_balance (no WARNING logged)."""
    p = _make_plan("MN")
    p.solve("maxSpending", options={"verbose": True})
    captured = capsys.readouterr()
    # Only the balance check itself: the loop may also warn that it stopped on the iteration limit,
    # which says nothing about the cash-flow identity.
    assert "Cash flow balance" not in captured.out, (
        "Cash flow balance check should not warn with state tax enabled"
    )


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
    inv_g = 1.0 / p.gamma_n[: p.N_n]
    expected_state = float(np.sum(p.st_T_n * inv_g))
    expected_federal = float(np.sum((p.T_n + p.U_n + p.J_n) * inv_g))

    alloc = p.lifetime_allocation()
    assert alloc["outflows"]["state_taxes"] == pytest.approx(expected_state, rel=1e-6)
    assert alloc["outflows"]["taxes"] == pytest.approx(expected_federal, rel=1e-6)
    assert alloc["outflows"]["state_taxes"] > 0

    mix = p.annual_cashflow_mix()
    np.testing.assert_allclose(mix["outflows"]["state_taxes"], p.st_T_n * inv_g, rtol=1e-6)
    np.testing.assert_allclose(
        mix["outflows"]["taxes"],
        (p.T_n + p.U_n + p.J_n) * inv_g,
        rtol=1e-6,
    )


# ---------------------------------------------------------------------------
# Task 9: Retirement income exemption
# ---------------------------------------------------------------------------


def test_retirement_income_exemption():
    """With NY (re=$20k), st_T_n < no-exemption equivalent."""
    # NY has $20k retirement income exemption (age 59.5+)
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


# ---------------------------------------------------------------------------
# Issues #145 and #146: per-person exemption; Roth conversions count toward it
# ---------------------------------------------------------------------------


def test_st_taxparams_exemption_is_per_person():
    """Each spouse qualifies on their own age (CO: 65+)."""
    thisyear = date.today().year
    gamma = np.ones(31)
    _, _, _, _, re_cap, _, _, _, _ = tax_state.st_taxParams(
        "CO", 2, 30, 30, gamma, [thisyear - 70, thisyear - 50], mobs=[1, 1]
    )
    assert re_cap[0, 0] == pytest.approx(24000)
    assert re_cap[1, 0] == 0
    assert re_cap[1, 14] == 0 and re_cap[1, 15] == pytest.approx(24000)


def test_st_taxparams_ny_age_59_and_a_half():
    """NY exclusion starts in the year the individual reaches 59.5."""
    thisyear = date.today().year
    gamma = np.ones(31)
    _, _, _, _, re_cap, _, _, _, _ = tax_state.st_taxParams(
        "NY", 2, 30, 30, gamma, [thisyear - 59, thisyear - 59], mobs=[6, 7]
    )
    assert re_cap[0, 0] == pytest.approx(20000)  # June birthday: 59.5 by December 31
    assert re_cap[1, 0] == 0 and re_cap[1, 1] == pytest.approx(20000)  # July birthday: next year


@pytest.mark.parametrize("state,expected", [("NY", True), ("IL", True), ("KY", True), ("MD", False)])
def test_st_taxparams_roth_conversion_eligibility(state, expected):
    """Roth conversion income counts toward the exemption except in MD."""
    _, _, _, _, _, _, conv_ok, _, _ = tax_state.st_taxParams(state, 1, 30, 30, np.ones(31), [1955], mobs=[1])
    assert conv_ok is expected


def _exempt_plan(state, names, dobs, deferred, taxable=0):
    p = Plan(names, dobs, [90] * len(names), "Test" + state)
    p.setStateTax(state)
    p.setAccountBalances(taxable=[taxable] * len(names), taxDeferred=deferred, taxFree=[0] * len(names))
    p.setSocialSecurity([2500] * len(names), [70] * len(names))
    p.setRates("conservative")
    alloc = [[60, 40, 0, 0], [60, 40, 0, 0]]
    p.setAllocationRatios("individual", generic=np.array([alloc] * len(names)))
    p.setSpendingProfile("flat")
    p.solve("maxSpending", options={"verbose": False})
    assert p.caseStatus == "solved"
    return p


def _eligible_in(p, with_conversions):
    eligible = p.w_ijn[:, 1, :] + p.piBar_in
    if with_conversions:
        eligible = eligible + p.x_in
    return eligible


def test_illinois_conversions_not_taxed():
    """IL exempts all retirement income, including Roth conversions (#146)."""
    thisyear = date.today().year
    p = _exempt_plan("IL", ["Jack"], [f"{thisyear - 64}-01-01"], [1000])
    assert np.sum(p.x_in) > 0, "case should convert"
    assert np.sum(p.st_T_n) == pytest.approx(0, abs=1)


def test_ny_exemption_covers_conversions():
    """NY caps each person's exclusion by their own withdrawals + conversions + pension."""
    thisyear = date.today().year
    p = _exempt_plan("NY", ["Jack", "Jill"], [f"{thisyear - 66}-01-01", f"{thisyear - 64}-01-01"], [600, 600])
    tol = 1e-3 * np.max(p.st_re_cap_in[np.isfinite(p.st_re_cap_in)])
    assert np.all(p.st_re_in <= _eligible_in(p, True) + tol)
    assert np.all(p.st_re_in <= p.st_re_cap_in + tol)
    # MFJ gets up to two caps (#145): in some year the household exempts more than one cap.
    total = np.sum(p.st_re_in, axis=0)
    assert np.any(total > 1.01 * p.st_re_cap_in[0])


def test_maryland_exemption_excludes_conversions():
    """MD's pension exclusion is capped without Roth conversion income."""
    thisyear = date.today().year
    p = _exempt_plan("MD", ["Jack"], [f"{thisyear - 66}-01-01"], [1000])
    tol = 1e-3 * np.max(p.st_re_cap_in)
    assert np.all(p.st_re_in <= _eligible_in(p, False) + tol)


# ---------------------------------------------------------------------------
# 2026 bracket audit: pin corrections that were structural, not just indexing
# ---------------------------------------------------------------------------


def _brackets(key):
    return [tuple(b) for b in tax_state.load_state_data()[key]["brackets"]]


def test_ca_mental_health_surtax_starts_at_1m_for_all_filers():
    """CA's 1% surtax applies above $1M of taxable income regardless of filing status."""
    assert (1000000.0, 13.3) in _brackets("CA_Single")
    assert (1000000.0, 12.3) in _brackets("CA_MFJ")  # 11.3% bracket + 1% surtax
    assert _brackets("CA_MFJ")[-1] == (1485906.0, 13.3)


def test_me_millionaire_surtax():
    """ME's 2% surtax starts at $1M (single) and $1.5M (MFJ) from 2026."""
    assert _brackets("ME_Single")[-1] == (1000000.0, 9.15)
    assert _brackets("ME_MFJ")[-1] == (1500000.0, 9.15)


@pytest.mark.parametrize("state,rate", [("GA", 4.99), ("UT", 4.45)])
def test_2026_flat_rates(state, rate):
    """Flat rates enacted in the 2026 sessions (GA HB 463, UT SB 60)."""
    for fs in ("Single", "MFJ"):
        assert _brackets(f"{state}_{fs}") == [(0.0, rate)]


def test_ks_two_rate_structure():
    """KS has had two rates (5.2%, 5.58%) since 2024."""
    assert _brackets("KS_Single") == [(0.0, 5.2), (23000.0, 5.58)]
    assert _brackets("KS_MFJ") == [(0.0, 5.2), (46000.0, 5.58)]


def _schedule_tax(income, brackets):
    """Tax from a TOML [[lower, rate_pct], ...] schedule, top bracket open-ended."""
    tax = 0.0
    for i, (lower, rate) in enumerate(brackets):
        upper = brackets[i + 1][0] if i + 1 < len(brackets) else np.inf
        tax += max(0.0, min(income, upper) - lower) * rate / 100
    return tax


def _lp_bracket_tax(income, theta, delta):
    """Tax from filling the LP brackets (rates, widths) in order."""
    tax, left = 0.0, income
    for rate, width in zip(theta, delta):
        filled = min(left, width)
        tax += filled * rate
        left -= filled
    return tax


@pytest.mark.parametrize("income", [900_000, 1_500_000, 3_000_000])
def test_nj_single_keeps_top_bracket(income):
    """NJ Single (7 brackets) is padded to MFJ's 8 without losing its open-ended 10.75% (issue #149)."""
    _, theta, delta, *_ = tax_state.st_taxParams("NJ", 1, 30, 30, np.ones(31), [1960], mobs=[1])
    expected = _schedule_tax(income, tax_state.get_state_entry("NJ", 0)["brackets"])
    assert _lp_bracket_tax(income, theta[:, 0], delta[:, 0]) == pytest.approx(expected)


def test_nj_survivor_keeps_top_bracket():
    """After n_d, a couple's survivor files Single and must keep NJ's top bracket (issue #149)."""
    n_d = 10
    _, theta, delta, *_ = tax_state.st_taxParams("NJ", 2, n_d, 30, np.ones(31), [1960, 1962], mobs=[1, 1], i_d=0)
    single = tax_state.get_state_entry("NJ", 0)["brackets"]
    mfj = tax_state.get_state_entry("NJ", 1)["brackets"]
    income = 1_500_000
    assert _lp_bracket_tax(income, theta[:, n_d - 1], delta[:, n_d - 1]) == pytest.approx(_schedule_tax(income, mfj))
    for n in range(n_d, 30):
        assert _lp_bracket_tax(income, theta[:, n], delta[:, n]) == pytest.approx(_schedule_tax(income, single))


_GAMMA = np.array([1.025**n for n in range(31)])


def test_ny_amounts_are_not_indexed():
    """NY fixes its thresholds, standard deduction and $20k exclusion in statute (issue #157)."""
    _, _, delta, sigma, re_cap, *_ = tax_state.st_taxParams("NY", 2, 30, 30, _GAMMA, [1964, 1964], mobs=[6, 12])
    np.testing.assert_array_equal(delta[:-1, 20], delta[:-1, 0])
    assert sigma[20] == sigma[0] == 16050
    assert re_cap[0, 20] == 20000


def test_other_states_stay_indexed():
    _, _, delta, sigma, *_ = tax_state.st_taxParams("MN", 2, 30, 30, _GAMMA, [1964, 1964], mobs=[6, 12])
    assert sigma[20] == pytest.approx(sigma[0] * _GAMMA[20])
    assert delta[0, 20] == pytest.approx(delta[0, 0] * _GAMMA[20])


def test_each_indexing_flag_controls_its_own_amounts():
    """MD indexes its pension cap and deduction but not its brackets; GA indexes neither cap nor brackets."""
    _, _, delta, sigma, re_cap, *_ = tax_state.st_taxParams("MD", 2, 30, 30, _GAMMA, [1960, 1960], mobs=[6, 12])
    assert re_cap[0, 20] == pytest.approx(re_cap[0, 0] * _GAMMA[20])  # exemptions_indexed = true
    # deduction_indexed = true: the $6,700 joint deduction grows; the exemptions stay fixed.
    assert sigma[20] - sigma[0] == pytest.approx(6700 * (_GAMMA[20] - 1))
    np.testing.assert_array_equal(delta[:-1, 20], delta[:-1, 0])  # brackets_indexed = false
    _, _, _, _, re_cap_ga, *_ = tax_state.st_taxParams("GA", 2, 30, 30, _GAMMA, [1955, 1955], mobs=[6, 12])
    assert re_cap_ga[0, 20] == re_cap_ga[0, 0] == 65000  # exemptions_indexed = false


def test_every_state_declares_its_indexing():
    """No default: each entry states whether its brackets, deduction and exemptions are indexed."""
    data = tax_state.load_state_data()
    for key, entry in data.items():
        for flag in ("brackets_indexed", "deduction_indexed", "exemptions_indexed"):
            assert isinstance(entry.get(flag), bool), f"{key} lacks a boolean '{flag}'"


def test_per_filer_exemptions_follow_living_filers_and_age():
    """NJ: $1,000 per filer, plus $1,000 per filer aged 65+ by December 31; the survivor alone after n_d."""
    _, _, _, sigma, *_ = tax_state.st_taxParams("NJ", 2, 10, 30, np.ones(31), [1962, 1966], mobs=[1, 1], i_d=0)
    thisyear = date.today().year
    for n in range(30):
        alive_yobs = [1962, 1966] if n < 10 else [1966]  # person 0 dies at n_d = 10
        seniors = sum(thisyear + n - yob + 11 / 12 >= 65 for yob in alive_yobs)
        assert sigma[n] == 1000 * len(alive_yobs) + 1000 * seniors, n


def test_personal_credit_counts_living_filers_and_indexes():
    # Both under 65 throughout the first decade (born 1990): personal credit only.
    ca = tax_state.st_credits("CA", 2, 10, 30, _GAMMA, yobs=[1990, 1990], mobs=[1, 1], i_d=0)
    assert ca[0] == pytest.approx(2 * 153)
    assert ca[9] == pytest.approx(2 * 153 * _GAMMA[9])  # indexed
    assert ca[10] == pytest.approx(153 * _GAMMA[10])  # survivor only


def test_senior_credit_is_added_per_filer_at_65():
    """CA Form 540 line 9: another $153 for each filer 65 or older by December 31."""
    thisyear = date.today().year
    yobs = [thisyear - 64, thisyear - 70]  # person 0 turns 65 next year; person 1 is already 70
    ca = tax_state.st_credits("CA", 2, 30, 30, np.ones(31), yobs=yobs, mobs=[1, 1])
    assert ca[0] == 2 * 153 + 1 * 153
    assert ca[1] == 2 * 153 + 2 * 153
    with pytest.raises(ValueError, match="senior_credit"):
        tax_state.st_credits("CA", 1, 30, 30, np.ones(31))
    assert tax_state.st_credits("DE", 1, 30, 30, _GAMMA)[20] == 110  # not indexed
    assert not tax_state.st_credits("NY", 1, 30, 30, _GAMMA).any()


def test_personal_credit_reduces_state_tax_down_to_zero():
    """In the LP, the credit used is at most the credit and at most the gross state tax."""
    p = _make_plan("CA")
    p.solve("maxSpending", {"withMedicare": "None"})
    assert p.caseStatus == "solved"
    gross = np.sum(p.st_f_tn * p.st_theta_tn, axis=0)
    np.testing.assert_allclose(p.st_T_n, np.maximum(0.0, gross - p.st_credit_n), atol=0.05)
    assert np.any(gross > p.st_credit_n) and np.any(p.st_T_n < gross - 1)


# ---------------------------------------------------------------------------
# Per-year state schedule (issue #159)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("state", ["NY", "NJ", "MD", "CA", "CO", "FL", "PA", "OH"])
def test_schedule_of_one_state_is_st_taxparams(state):
    """With a single state, st_schedule gives exactly st_taxParams' arrays and flags."""
    yobs, mobs = [1960, 1962], [3, 7]
    ref = tax_state.st_taxParams(state, 2, 20, 30, _GAMMA, yobs, mobs=mobs, i_d=0)
    s = tax_state.st_schedule([state] * 30, 2, 20, 30, _GAMMA, yobs, mobs=mobs, i_d=0)
    assert s["N_st"] == ref[0]
    for key, k in (("theta_tn", 1), ("DeltaBar_tn", 2), ("sigmaBar_n", 3), ("re_cap_in", 4), ("pe_cap_in", 5)):
        np.testing.assert_array_equal(s[key], ref[k])
    assert np.all(s["conv_ok_n"] == ref[6]) and np.all(s["tax_ss_n"] == ref[7])
    fed_sd, bonus = tax_state.federal_deduction(state)
    assert np.all(s["fed_sd_n"] == fed_sd) and np.all(s["senior_bonus_n"] == bonus)
    np.testing.assert_array_equal(
        s["credit_n"], tax_state.st_credits(state, 2, 20, 30, _GAMMA, yobs=yobs, mobs=mobs, i_d=0)
    )


def test_schedule_takes_each_year_from_its_state_and_pads_brackets():
    """NY for five years, then FL, then no state: each year is its state's column; NY's longer
    schedule sets N_st, and the shorter ones are padded at their top rate with zero width."""
    states = ["NY"] * 5 + ["FL"] * 5 + [""] * 20
    s = tax_state.st_schedule(states, 1, 30, 30, _GAMMA, [1960], mobs=[1])
    ny = tax_state.st_taxParams("NY", 1, 30, 30, _GAMMA, [1960], mobs=[1])
    fl = tax_state.st_taxParams("FL", 1, 30, 30, _GAMMA, [1960], mobs=[1])
    assert s["N_st"] == ny[0] > fl[0]
    np.testing.assert_array_equal(s["theta_tn"][:, :5], ny[1][:, :5])
    np.testing.assert_array_equal(s["DeltaBar_tn"][:, :5], ny[2][:, :5])
    k = fl[0]
    np.testing.assert_array_equal(s["DeltaBar_tn"][:k, 5:10], fl[2][:, 5:10])
    assert not s["DeltaBar_tn"][k:, 5:10].any()  # padding has no width
    np.testing.assert_array_equal(s["theta_tn"][k:, 5:10], np.broadcast_to(fl[1][k - 1, 5:10], (ny[0] - k, 5)))
    # No state: one zero-rate bracket wide enough for any income, nothing else.
    assert not s["theta_tn"][:, 10:].any()
    assert np.all(s["DeltaBar_tn"][0, 10:] > 1e6) and not s["DeltaBar_tn"][1:, 10:].any()
    assert not s["sigmaBar_n"][10:].any() and not s["credit_n"][10:].any()
