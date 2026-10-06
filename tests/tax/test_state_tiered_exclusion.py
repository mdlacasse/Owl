"""NJ pension/retirement and other retirement income exclusions (NJ-1040 lines 28a-28c, Worksheet D, 2025)."""

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import tax_state

THISYEAR = owl.Plan(["A"], ["1960-01-01"], [80], "t", verbose=False).year_n[0]

# The line 28a chart: income on line 27 up to the ceiling -> share of line 20a excluded.
MFJ_CHART = [(100_000, 1.0), (125_000, 0.5), (150_000, 0.25)]
SINGLE_CHART = [(100_000, 1.0), (125_000, 0.375), (150_000, 0.1875)]


@pytest.mark.parametrize("filing,chart,cap", [(1, MFJ_CHART, 100_000), (0, SINGLE_CHART, 75_000)])
def test_data_is_the_printed_chart(filing, chart, cap):
    entry = tax_state.get_state_entry("NJ", filing)
    assert tax_state._read_exclusion_tiers(entry) == chart
    assert entry["retirement_exclusion_cap"] == cap
    assert entry["retirement_exclusion_age"] == 62
    assert entry["retirement_exclusion_earned_limit"] == 3000


def test_only_new_jersey_has_an_income_tiered_exclusion():
    for s in tax_state.valid_states():
        for filing in (0, 1):
            assert ("retirement_exclusion_tiers" in tax_state.get_state_entry(s, filing)) == (s == "NJ")


@pytest.mark.parametrize(
    "income,share",
    [(0, 1.0), (100_000, 1.0), (100_001, 0.5), (125_000, 0.5), (125_001, 0.25), (150_000, 0.25), (150_001, 0.0)],
)
def test_share_steps_at_each_ceiling(income, share):
    limits, shares = np.array([c for c, _ in MFJ_CHART]), np.array([s for _, s in MFJ_CHART])
    assert tax_state.exclusion_share(income, limits, shares) == share


def test_params_are_nominal_and_switch_to_the_single_chart_after_a_death():
    gamma = np.array([1.03**n for n in range(31)])
    p = tax_state.st_taxParams("NJ", 2, 10, 30, gamma, [1962, 1963], mobs=[6, 12], i_d=0)
    assert np.all(p.rx_limit_kn[:, :10].T == [100_000, 125_000, 150_000])
    assert np.all(p.rx_limit_kn[:, 10:].T == [100_000, 125_000, 150_000])
    assert np.all(p.rx_share_kn[:, :10].T == [1.0, 0.5, 0.25])
    assert np.all(p.rx_share_kn[:, 10:].T == [1.0, 0.375, 0.1875])
    assert np.all(p.rx_cap_n[:10] == 100_000) and np.all(p.rx_cap_n[10:] == 75_000)
    assert np.all(p.rx_age_n == 62) and np.all(p.rx_earned_n == 3000)
    mn = tax_state.st_taxParams("MN", 2, 10, 30, gamma, [1962, 1963], mobs=[6, 12])
    assert np.all(mn.rx_cap_n == 0)


def test_schedule_takes_the_exclusion_only_from_the_years_in_new_jersey():
    p = tax_state.st_schedule(["NY"] * 5 + ["NJ"] * 25, 2, 30, 30, np.ones(31), [1962, 1963], mobs=[6, 12])
    assert np.all(p.rx_cap_n[:5] == 0) and np.all(p.rx_cap_n[5:] == 100_000)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _pension_plan(pension, births=("1962-06-15", "1963-12-15"), ages=(62, 62), moves=()):
    """Fixed pension income and nothing to choose, solved for bequest at a fixed spending."""
    p = owl.Plan(["Joe", "Jane"], list(births), [85, 85], "NJ exclusion", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[0, 0])
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
    p.setRates("conservative")
    p.setSocialSecurity([2800, 2200], [70, 70])
    p.setPension(list(pension), list(ages), [False, False])
    p.setStateTax("NJ", moves)
    options = {"noRothConversions": "None", "maxRothConversion": 0, "withMedicare": "None", "netSpending": 35}
    p.solve("maxBequest", options=options)
    assert p.caseStatus == "solved"
    return p


def _statutory_tax(p, n):
    """NJ tax on the plan's own line 27 income, by the chart (lines 28-29) and the exemptions (line 30)."""
    exclusion = p._tiered_exclusion_implied()[1][n]
    taxable = max(0.0, np.round(p.st_agi_n[n]) - exclusion - p.st_sigmaBar_n[n])
    return tax_state.bracket_tax(taxable, p.st_theta_tn[:, n], p.st_DeltaBar_tn[:, n])


@pytest.mark.parametrize(
    "pension,share",
    [([3000, 2000], 1.0), ([5000, 4000], 0.5), ([6500, 4500], 0.25), ([8000, 5000], 0.0)],
)
def test_plan_charges_the_statutory_tax_in_each_tier(pension, share):
    p = _pension_plan(pension)
    for n in range(5):  # before Social Security; both 62+ and no wages, so line 28b applies
        assert p.st_rx_other_n[n]
        assert p._tiered_exclusion_implied()[0][n] == share
        assert p.st_T_n[n] == pytest.approx(_statutory_tax(p, n), abs=1.0)
        if 0 < share < 1:
            assert p.st_rx_n[n] == pytest.approx(share * p.st_agi_n[n], abs=1.0)  # Worksheet D: share of line 27


def test_tier_one_by_hand():
    """Line 27 of about 108,000 (married, both 62+): half of it excluded, the rest less 2,000 exemptions."""
    p = _pension_plan([5000, 4000])
    L = p.st_agi_n[0]
    assert 100_000 < L < 125_000
    taxable = L / 2 - 2000
    tax = 0.014 * 20_000 + 0.0175 * 30_000 + 0.0245 * (taxable - 50_000)  # Table B
    assert p.st_T_n[0] == pytest.approx(tax, abs=1.0)


def test_only_line_28a_while_one_spouse_is_under_62():
    """Jane (born 1966) draws a pension from 60 but is eligible only from 62: until then only Joe's pension
    is excluded, and line 28b is closed to the couple."""
    p = _pension_plan([5000, 2500], births=("1962-06-15", "1966-12-15"), ages=(62, 60))
    young = [n for n in range(5) if THISYEAR + n - 1966 < 62]
    assert young
    for n in young:
        assert not p.st_rx_other_n[n] and list(p.st_rx_elig_in[:, n]) == [True, False]
        assert p.st_rx_n[n] == pytest.approx(p.piBar_in[0, n], abs=1.0)  # Joe's pension, under the cap
        assert p.st_T_n[n] > 0
    n = young[-1] + 1
    assert p.st_rx_other_n[n] and p.st_T_n[n] == pytest.approx(0.0, abs=1.0)


def test_nothing_is_excluded_before_62():
    p = _pension_plan([3000, 2000], births=("1966-06-15", "1967-12-15"), ages=(55, 55))
    first = 62 + 1966 - THISYEAR
    assert np.all(p.st_rx_n[:first] == 0) and p.st_rx_n[first] > 0


def _couple(tiers=True, monkeypatch=None, tax_deferred=(900, 600), **opts):
    """A couple with tax-deferred savings to convert or draw, so income in each year is a choice."""
    if not tiers:
        monkeypatch.setattr(tax_state, "_read_exclusion_tiers", lambda entry: [])
    p = owl.Plan(["Joe", "Jane"], ["1964-03-15", "1965-09-15"], [89, 92], "NJ couple", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[150, 150], taxDeferred=list(tax_deferred), taxFree=[75, 75])
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
    p.setRates("conservative")
    p.setSocialSecurity([3000, 2400], [70, 70])
    p.setStateTax("NJ")
    p.solve("maxSpending", options={"withMedicare": "None", "withSSTaxability": 0.85, "bequest": 0, **opts})
    assert p.caseStatus == "solved"
    return p


def test_optimizer_holds_income_at_the_ceiling_and_the_tax_is_statutory(monkeypatch):
    p = _couple()
    held = [n for n in range(p.N_n) if abs(p.st_agi_n[n] - 100_000) <= 1.0]
    assert len(held) >= 3, "income parked exactly at the first ceiling"
    for n in range(p.N_n):
        assert p.st_T_n[n] == pytest.approx(_statutory_tax(p, n), abs=1.0)
    without = _couple(tiers=False, monkeypatch=monkeypatch)
    assert not without._rx_active
    assert p.basis > without.basis
    assert np.sum(p.st_T_n / p.gamma_n[:-1]) < np.sum(without.st_T_n / without.gamma_n[:-1]) - 10_000


def test_local_search_keeps_the_tiers_integral():
    """breakpointMethod="local-search" (upstream 2026.10.6) pins and searches the tier binaries like its
    other families. Its LP start used to relax them, and the plan it returned held fractional tiers,
    with a tax that differed from the statute's in most years."""
    p = _couple(breakpointMethod="local-search", localSearchTime=1)
    assert p.breakpointMethodUsed.startswith("local search")
    for n in range(p.N_n):
        assert p.st_T_n[n] == pytest.approx(_statutory_tax(p, n), abs=1.0)


def test_move_to_new_jersey_excludes_only_there():
    p = _pension_plan([5000, 4000], moves=[(THISYEAR + 3, "FL")])
    assert np.all(p.st_rx_n[:3] > 0) and np.all(p.st_rx_n[3:] == 0)


def test_explanation_reports_the_exclusion():
    from owlplanner.assistant.explain import build_explanation
    from owlplanner.assistant.explain_schema import PlanExplanation

    p = _couple(withDuals=True)  # duals come from re-solving with the tier binaries fixed
    ex = build_explanation(p)
    PlanExplanation.model_validate(ex)
    rows = ex["state_tax_brackets"]["by_year"]
    assert any(r.get("retirement_exclusion_today", 0) > 0 for r in rows)
    held = [r for r in rows if "exclusion_ceiling_today" in r]
    assert held and all(r["exclusion_ceiling_today"] > 0 for r in held)


def test_years_far_above_the_ceilings_are_left_out_and_claim_nothing():
    """Pensions of $324,000: every year is above RX_WINDOW times the top ceiling, so no tier binaries are
    freed; the statute excludes nothing there either."""
    from owlplanner.plan import RX_WINDOW

    p = _pension_plan([25000, 2000])
    assert np.all(p.st_agi_n[:5] > RX_WINDOW * 150_000)
    assert not np.any(p.RXF_n[:5] >= 0.5) and np.all(p.st_rx_n == 0)
    for n in range(5):
        assert p.st_T_n[n] == pytest.approx(_statutory_tax(p, n), abs=1.0)


def test_free_set_only_grows_and_holds_the_years_near_the_ceilings():
    p = _couple()
    near = p.st_rx_elig_in.any(axis=0) & (p.st_agi_n <= 225_000)
    assert np.all(p.RXF_n[near] >= 0.5), "every eligible year near the ceilings has free tier binaries"


def test_time_limit_keeps_the_tiers_and_reports_the_gap():
    """A $2.5M couple does not prove optimal quickly. With a short maxTime the first MILP stops on the
    limit, later iterations keep its tiers, the plan's gap is that MILP's, and the tax stays statutory."""
    p = _couple(tax_deferred=(1500, 1000), maxTime=2)
    assert p._rx_fixed is not None
    assert p.solverGap >= p._rx_fixed[2] > 1e-4
    for n in range(p.N_n):
        assert p.st_T_n[n] == pytest.approx(_statutory_tax(p, n), abs=1.0)


def test_node_limit_keeps_the_tiers_and_gives_the_same_plan_every_time(monkeypatch):
    """Without maxTime the MILP stops at RX_NODE_LIMIT nodes, not at a time: the plan does not depend on
    machine speed or load. Later iterations keep its tiers, as with a time limit."""
    from owlplanner import plan as plan_module

    monkeypatch.setattr(plan_module, "RX_NODE_LIMIT", 200)
    a, b = (_couple(tax_deferred=(1500, 1000)) for _ in range(2))
    assert a._rx_fixed is not None and a.solverGap >= a._rx_fixed[2] > 1e-4
    assert a.basis == b.basis and np.array_equal(a.st_rx_n, b.st_rx_n)
    for n in range(a.N_n):
        assert a.st_T_n[n] == pytest.approx(_statutory_tax(a, n), abs=1.0)


@pytest.mark.parametrize(
    "income,kept,expected",
    [
        (150_000.0, 3, 2),  # on the floor of "above the last ceiling": the statute's 25% tier
        (150_000.4, 3, 2),  # line 27 is in whole dollars
        (150_001.0, 3, 3),  # above the ceiling: the kept tier is the statute's
        (100_000.0, 1, 0),  # on the floor of the 50% tier: the 100% tier
        (125_000.0, 1, 1),  # on the ceiling of the kept tier: already the statute's
        (90_000.0, 0, 0),
    ],
)
def test_kept_tier_moves_down_to_the_statute_on_its_floor(income, kept, expected):
    """A tier kept from a time-limited MILP bounds income from below; income held on that floor belongs,
    by the statute, to the tier below. Only that downward move is made, never one up."""
    p = _pension_plan([3000, 2000])
    n = int(np.flatnonzero(p.st_rx_elig_in.any(axis=0))[0])
    zx = np.zeros((p.N_n, p.st_rx_limit_kn.shape[0] + 1))
    zx[n, kept] = 1.0
    p._rx_fixed = (zx, np.ones(p.N_n, dtype=bool), 0.0)
    p.st_agi_n = p.st_agi_n.copy()
    p.st_agi_n[n] = income
    moved = p._refix_boundary_tiers()
    assert moved[n] == (expected != kept)
    assert int(np.argmax(p._rx_fixed[0][n])) == expected
    assert moved.sum() == moved[n]
