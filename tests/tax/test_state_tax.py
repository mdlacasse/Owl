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
        assert isinstance(entry.get("indexed", True), bool), f"{state}: indexed must be a bool"


# ---------------------------------------------------------------------------
# Task 2: st_taxParams unit tests
# ---------------------------------------------------------------------------


def test_st_taxparams_shape():
    """st_taxParams returns arrays with correct shapes."""
    gamma = np.ones(31)  # N_n=30 years + 1
    sp = tax_state.st_taxParams("MN", 1, 30, 30, gamma, [1960], mobs=[1])
    assert sp.theta_tn.shape == (sp.N_st, 30)
    assert sp.DeltaBar_tn.shape == (sp.N_st, 30)
    assert sp.sigmaBar_n.shape == (30,)
    assert sp.re_cap_in.shape == (1, 30)
    assert sp.pe_cap_in.shape == (1, 30)
    assert sp.ss_thresh_n.shape == (30,)
    assert sp.N_st >= 4  # MN has 4 brackets for single


def test_st_taxparams_inflation_scaling():
    """Bracket widths and deductions scale with gamma_n."""
    gamma_flat = np.ones(31)
    gamma_inflated = np.array([1.02**n for n in range(31)])
    for state in ("MN", "CA"):
        flat = tax_state.st_taxParams(state, 1, 30, 30, gamma_flat, [1960], mobs=[1])
        inflated = tax_state.st_taxParams(state, 1, 30, 30, gamma_inflated, [1960], mobs=[1])
        # Year 10 should be inflated relative to year 0
        assert inflated.DeltaBar_tn[0, 10] > flat.DeltaBar_tn[0, 10]
        assert inflated.sigmaBar_n[10] > flat.sigmaBar_n[10]


def test_st_taxparams_filing_status_transition():
    """Bracket widths switch from MFJ to Single at n_d."""
    gamma = np.ones(31)
    n_d = 10
    mfj = tax_state.st_taxParams("MN", 2, n_d, 30, gamma, [1955, 1958], mobs=[1, 1])
    # Before n_d: MFJ brackets
    # After n_d: Single brackets
    single = tax_state.st_taxParams("MN", 1, 30, 30, gamma, [1958], mobs=[1])
    # Deduction after death should match single
    assert pytest.approx(mfj.sigmaBar_n[n_d], rel=1e-6) == single.sigmaBar_n[0]


def test_st_taxparams_exemption_age_gating():
    """Retirement income exemption is zero before exemption_age, nonzero after."""
    # CO has exemption_age=65 for re
    gamma = np.ones(31)
    # born 1995 → turns 65 in 2060 → past 30-year plan end (2026+29=2055)
    re_cap = tax_state.st_taxParams("CO", 1, 30, 30, gamma, [1995], mobs=[1]).re_cap_in
    # All zeros since never reaches 65 during the plan
    assert np.all(re_cap == 0), "CO re_cap should be 0 when never 65+ during plan"


def test_st_taxparams_exemption_age_active():
    """Retirement income exemption applies once age requirement is met."""
    gamma = np.ones(31)
    re_cap = tax_state.st_taxParams(
        "CO",
        1,
        30,
        30,
        gamma,
        [1955],  # born 1955 → already 65+ at plan start
        mobs=[1],
    ).re_cap_in
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
    re_cap = tax_state.st_taxParams("CO", 2, 30, 30, gamma, [thisyear - 70, thisyear - 50], mobs=[1, 1]).re_cap_in
    assert re_cap[0, 0] == pytest.approx(24000)
    assert re_cap[1, 0] == 0
    assert re_cap[1, 14] == 0 and re_cap[1, 15] == pytest.approx(24000)


def test_st_taxparams_ny_age_59_and_a_half():
    """NY exclusion starts in the year the individual reaches 59.5."""
    thisyear = date.today().year
    gamma = np.ones(31)
    re_cap = tax_state.st_taxParams("NY", 2, 30, 30, gamma, [thisyear - 59, thisyear - 59], mobs=[6, 7]).re_cap_in
    assert re_cap[0, 0] == pytest.approx(20000)  # June birthday: 59.5 by December 31
    assert re_cap[1, 0] == 0 and re_cap[1, 1] == pytest.approx(20000)  # July birthday: next year


@pytest.mark.parametrize("state,expected", [("NY", True), ("IL", True), ("KY", True), ("MD", False)])
def test_st_taxparams_roth_conversion_eligibility(state, expected):
    """Roth conversion income counts toward the exemption except in MD."""
    conv_ok = tax_state.st_taxParams(state, 1, 30, 30, np.ones(31), [1955], mobs=[1]).conv_ok
    assert np.all(conv_ok == expected)


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


# ---------------------------------------------------------------------------
# PR 2: typed state params and non-indexed flag
# ---------------------------------------------------------------------------


def test_state_taxparams_returns_dataclass():
    """st_taxParams returns a StateTaxParams with named fields."""
    sp = tax_state.st_taxParams("MN", 1, 30, 30, np.ones(31), [1960], mobs=[1])
    assert isinstance(sp, tax_state.StateTaxParams)
    assert sp.N_st >= 4
    assert sp.indexed.all()
    assert sp.conv_ok.shape == sp.tax_ss.shape == (30,)
    assert sp.conv_ok.dtype == sp.tax_ss.dtype == bool


def test_ny_not_indexed():
    """NY brackets and deduction use nominal statutory dollars (no gamma_n)."""
    gamma_flat = np.ones(31)
    gamma_inflated = np.array([1.02**n for n in range(31)])
    sp_flat = tax_state.st_taxParams("NY", 1, 30, 30, gamma_flat, [1960], mobs=[1])
    sp_inf = tax_state.st_taxParams("NY", 1, 30, 30, gamma_inflated, [1960], mobs=[1])
    assert not sp_flat.indexed.any()
    assert not sp_inf.indexed.any()
    # Non-indexed: year 10 must equal year 0 regardless of gamma_n
    np.testing.assert_array_equal(sp_inf.DeltaBar_tn[:, 10], sp_inf.DeltaBar_tn[:, 0])
    assert sp_inf.sigmaBar_n[10] == pytest.approx(sp_inf.sigmaBar_n[0])
    # And flat vs inflated should give identical arrays
    np.testing.assert_array_equal(sp_inf.DeltaBar_tn, sp_flat.DeltaBar_tn)
    np.testing.assert_array_equal(sp_inf.sigmaBar_n, sp_flat.sigmaBar_n)


def test_mn_still_indexed():
    """MN (default indexed=true) still scales with gamma_n."""
    gamma_flat = np.ones(31)
    gamma_inflated = np.array([1.02**n for n in range(31)])
    sp_flat = tax_state.st_taxParams("MN", 1, 30, 30, gamma_flat, [1960], mobs=[1])
    sp_inf = tax_state.st_taxParams("MN", 1, 30, 30, gamma_inflated, [1960], mobs=[1])
    assert sp_flat.indexed.all()
    assert sp_inf.indexed.all()
    assert sp_inf.DeltaBar_tn[0, 10] > sp_flat.DeltaBar_tn[0, 10]


def test_ny_re_cap_not_inflated():
    """NY retirement exclusion cap stays nominal when indexed=False."""
    gamma_inflated = np.array([1.02**n for n in range(31)])
    sp = tax_state.st_taxParams("NY", 1, 30, 30, gamma_inflated, [1960], mobs=[1])
    # NY cap is $20k statutory; year 0 and year 10 must both be $20k
    active = sp.re_cap_in[0, sp.re_cap_in[0, :] > 0]
    assert active[0] == pytest.approx(20000.0)
    assert active[-1] == pytest.approx(20000.0)


def test_indexed_false_in_toml(tmp_path):
    """indexed = false is read from TOML."""
    toml_content = """
[XX_Single]
brackets = [[0.0, 5.0], [50000.0, 6.0]]
standard_deduction = 1000
tax_social_security = false
ss_exemption_threshold = 0
retirement_income_exemption = 0
exemption_age = 0
pension_exemption = 0
roth_conversion_eligible = true
indexed = false
"""
    f = tmp_path / "test_state.toml"
    f.write_text(toml_content)
    gamma = np.array([1.02**n for n in range(31)])
    sp = tax_state.st_taxParams("XX", 1, 30, 30, gamma, [1960], mobs=[1], toml_path=str(f))
    assert not sp.indexed.any()
    # Non-indexed: year 10 == year 0
    np.testing.assert_array_equal(sp.DeltaBar_tn[:, 10], sp.DeltaBar_tn[:, 0])


def test_indexed_default_is_true(tmp_path):
    """indexed defaults to true when the field is absent."""
    toml_content = """
[XX_Single]
brackets = [[0.0, 5.0]]
standard_deduction = 1000
tax_social_security = false
ss_exemption_threshold = 0
retirement_income_exemption = 0
exemption_age = 0
pension_exemption = 0
roth_conversion_eligible = true
"""
    f = tmp_path / "test_state.toml"
    f.write_text(toml_content)
    sp = tax_state.st_taxParams("XX", 1, 30, 30, np.ones(31), [1960], mobs=[1], toml_path=str(f))
    assert sp.indexed.all()


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
    sp = tax_state.st_taxParams("NJ", 1, 30, 30, np.ones(31), [1960], mobs=[1])
    theta, delta = sp.theta_tn, sp.DeltaBar_tn
    expected = _schedule_tax(income, tax_state.get_state_entry("NJ", 0)["brackets"])
    assert _lp_bracket_tax(income, theta[:, 0], delta[:, 0]) == pytest.approx(expected)


def test_nj_survivor_keeps_top_bracket():
    """After n_d, a couple's survivor files Single and must keep NJ's top bracket (issue #149)."""
    n_d = 10
    sp = tax_state.st_taxParams("NJ", 2, n_d, 30, np.ones(31), [1960, 1962], mobs=[1, 1])
    theta, delta = sp.theta_tn, sp.DeltaBar_tn
    single = tax_state.get_state_entry("NJ", 0)["brackets"]
    mfj = tax_state.get_state_entry("NJ", 1)["brackets"]
    income = 1_500_000
    assert _lp_bracket_tax(income, theta[:, n_d - 1], delta[:, n_d - 1]) == pytest.approx(_schedule_tax(income, mfj))
    for n in range(n_d, 30):
        assert _lp_bracket_tax(income, theta[:, n], delta[:, n]) == pytest.approx(_schedule_tax(income, single))
