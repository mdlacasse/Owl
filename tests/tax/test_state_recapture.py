"""NY benefit recapture (Tax Law sec. 601(d)): the tax computation worksheets of the IT-201-I."""

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import tax_state

START, WIDTH, UNTIL = 107_650.0, 50_000.0, 5_000_000.0

# Rate schedules printed in the 2025 IT-201-I (page 34), the year whose worksheets we can check.
MFJ_2025 = [(0, 4), (17150, 4.5), (23600, 5.25), (27900, 5.5), (161550, 6), (323200, 6.85),
            (2155350, 9.65), (5000000, 10.3)]
SINGLE_2025 = [(0, 4), (8500, 4.5), (11700, 5.25), (13900, 5.5), (80650, 6), (215400, 6.85),
               (1077550, 9.65), (5000000, 10.3)]


def _arrays(brackets):
    return tax_state._brackets_to_rates_and_widths([[lo, r] for lo, r in brackets], 5e6)


def _rec(brackets, agi, ti, **kw):
    theta, Delta = _arrays(brackets)
    return tax_state.state_recapture(agi, ti, theta, Delta, START, WIDTH, UNTIL, **kw)


# Recapture Base amount and Incremental Benefit amount printed on the worksheets:
# (threshold where the tier starts, base, incremental)
MFJ_WORKSHEETS = [(161550, 333, 807), (323200, 1140, 2747), (2155350, 3887, 60350), (5000000, 64237, 32500)]
SINGLE_WORKSHEETS = [(215400, 568, 1831), (1077550, 2399, 30172), (5000000, 32571, 32500)]


@pytest.mark.parametrize("brackets,sheets", [(MFJ_2025, MFJ_WORKSHEETS), (SINGLE_2025, SINGLE_WORKSHEETS)])
def test_tier_amounts_match_the_printed_worksheet_constants(brackets, sheets):
    for L, base, incremental in sheets:
        ti = L + 1000
        assert _rec(brackets, L, ti) == pytest.approx(base, abs=1.0)  # AGI at the threshold: nothing phased in
        assert _rec(brackets, L + WIDTH, ti) - _rec(brackets, L, ti) == pytest.approx(incremental, abs=1.0)
        assert _rec(brackets, L + 10 * WIDTH, ti) == _rec(brackets, L + WIDTH, ti)  # fully phased in


def test_married_worksheet_1_by_hand():
    """AGI 120,000, taxable income 100,000: worksheet 1 lines 1-9."""
    tax = 1202 + 0.055 * (100_000 - 27_900)  # line 4
    line5 = 0.055 * 100_000 - tax
    line7 = round((120_000 - 107_650) / 50_000, 4)
    expected = line5 * line7
    assert _rec(MFJ_2025, 120_000, 100_000, round_phase=True) == pytest.approx(expected)
    assert expected == pytest.approx(82.13, abs=0.01)


@pytest.mark.parametrize("brackets,flat", [(MFJ_2025, 0.055), (SINGLE_2025, 0.06)])
def test_first_tier_ends_at_the_flat_rate_of_the_start_bracket(brackets, flat):
    """From AGI 157,650 the whole taxable income is taxed at the rate of the bracket holding 107,650."""
    theta, Delta = _arrays(brackets)
    ti = 120_000.0
    total = tax_state.bracket_tax(ti, theta, Delta) + _rec(brackets, 157_650, ti)
    assert total == pytest.approx(flat * ti)


@pytest.mark.parametrize("brackets", [MFJ_2025, SINGLE_2025])
def test_nothing_at_or_below_the_start(brackets):
    assert _rec(brackets, START, 90_000) == 0.0
    assert _rec(brackets, 50_000, 40_000) == 0.0


@pytest.mark.parametrize("brackets", [MFJ_2025, SINGLE_2025])
def test_continuous_in_agi(brackets):
    eps = 1e-3
    for L in [lo for lo, _ in brackets if lo > START] + [START]:
        for agi in (L, L + WIDTH):
            for ti in (100_000, L + 500):
                assert abs(_rec(brackets, agi + eps, ti) - _rec(brackets, agi, ti)) < 0.01


@pytest.mark.parametrize("brackets", [MFJ_2025, SINGLE_2025])
def test_taxable_income_crossing_a_threshold_jumps_by_the_phased_in_increment(brackets):
    """Worksheet 1 or 7 turns into the next one at a threshold L, and the printed worksheets do not join up:
    once AGI is above L, crossing L adds the phased-in part of the Incremental Benefit amount. With the
    phase-in complete the whole taxable income moves to the higher flat rate, which is the notch."""
    eps = 1e-3
    L = min(lo for lo, _ in brackets if lo > START)
    k = [lo for lo, _ in brackets].index(L)
    theta, _ = _arrays(brackets)
    incremental = (theta[k] - theta[k - 1]) * L
    for share in (0.0, 0.25, 1.0, 3.0):
        agi = L + share * WIDTH
        jump = _rec(brackets, agi, L + eps) - _rec(brackets, agi, L - eps)
        assert jump == pytest.approx(incremental * min(share, 1.0), abs=0.01)


@pytest.mark.parametrize("brackets", [MFJ_2025, SINGLE_2025])
def test_recapture_never_decreases_with_agi(brackets):
    ti = 300_000.0
    values = [_rec(brackets, agi, ti) for agi in np.linspace(100_000, 600_000, 60)]
    assert all(b >= a - 1e-9 for a, b in zip(values, values[1:]))


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def test_new_york_declares_recapture_and_no_other_state_does():
    for filing in (0, 1):
        assert tax_state.get_state_entry("NY", filing)["recapture_agi_start"] == 107650
    others = [s for s in tax_state.valid_states() if s != "NY"]
    for s in others:
        for filing in (0, 1):
            assert "recapture_agi_start" not in tax_state.get_state_entry(s, filing)


def test_params_carry_recapture_and_do_not_inflate_it():
    gamma = np.array([1.03**n for n in range(31)])
    ny = tax_state.st_taxParams("NY", 2, 30, 30, gamma, [1964, 1964], mobs=[6, 12])
    assert np.all(ny.recap_start_n == 107650) and np.all(ny.recap_width_n == 50000)
    assert np.all(ny.recap_until_n == 5_000_000)
    mn = tax_state.st_taxParams("MN", 2, 30, 30, gamma, [1964, 1964], mobs=[6, 12])
    assert np.all(np.isinf(mn.recap_start_n))


def test_schedule_takes_recapture_only_from_the_years_in_new_york():
    gamma = np.ones(31)
    p = tax_state.st_schedule(["NY"] * 5 + ["FL"] * 25, 2, 30, 30, gamma, [1964, 1964], mobs=[6, 12])
    assert np.all(np.isfinite(p.recap_start_n[:5])) and np.all(np.isinf(p.recap_start_n[5:]))


def test_2026_tier_amounts_follow_from_the_2026_rates():
    """2026 cut the first five rates; the amounts come from the brackets, so they move with them."""
    p = tax_state.st_taxParams("NY", 2, 30, 30, np.ones(31), [1964, 1964], mobs=[6, 12])
    theta, Delta = p.theta_tn[:, 0], p.DeltaBar_tn[:, 0]
    L = 161_550.0
    tax = tax_state.bracket_tax(L, theta, Delta)
    assert theta[3] == pytest.approx(0.054) and theta[4] == pytest.approx(0.059)
    base = tax_state.state_recapture(L, L + 1000, theta, Delta, 107650.0, 50000.0, 5e6)
    assert base == pytest.approx(0.054 * L - tax)
    full = tax_state.state_recapture(L + 50000, L + 1000, theta, Delta, 107650.0, 50000.0, 5e6)
    assert full - base == pytest.approx((0.059 - 0.054) * L)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _plan(pension, state="NY", moves=(), locality=""):
    """Fixed pension income and nothing else to choose, solved for bequest at a fixed spending."""
    p = owl.Plan(["Joe", "Jane"], ["1964-06-15", "1964-12-15"], [85, 85], "Recapture")
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[0, 0])
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
    p.setRates("conservative")
    p.setSocialSecurity([2800, 2200], [70, 70])
    p.setPension(pension, [62, 62], [False, False])
    p.setStateTax(state, moves, locality)
    options = {"noRothConversions": "None", "maxRothConversion": 0, "withMedicare": "None", "netSpending": 35}
    p.solve("maxBequest", options=options)
    assert p.caseStatus == "solved"
    return p


def _worksheet_tax(p, n):
    theta, Delta = p.st_theta_tn[:, n], p.st_DeltaBar_tn[:, n]
    start, width, until = (a[n] for a in p.st_recap)
    ti = p.st_ti_n[n]
    return tax_state.bracket_tax(ti, theta, Delta) + tax_state.state_recapture(
        p.st_agi_n[n], ti, theta, Delta, start, width, until
    )


@pytest.mark.parametrize("pension,tier", [([10000, 6000], "phase-in"), ([14000, 8000], "second tier")])
def test_plan_charges_the_worksheet_tax(pension, tier):
    p = _plan(pension)
    years = range(1, 6)  # before Social Security starts, so state AGI is federal AGI less the exclusions
    for n in years:
        assert p.st_agi_n[n] == pytest.approx(p.MAGI_n[n] - 2 * 20_000, abs=1.0), "20k pension exclusion each"
        assert p.st_recap_n[n] > 0
        assert p.st_T_n[n] == pytest.approx(_worksheet_tax(p, n), abs=1.0)
    if tier == "phase-in":
        assert 107_650 < p.st_agi_n[1] < 157_650 and p.st_recap_n[1] < 332.5
    else:
        assert p.st_agi_n[1] > 161_550 and p.st_recap_n[1] == pytest.approx(1140.2, abs=1.0)


def test_loop_converges_on_the_recapture():
    p = _plan([10000, 6000])
    assert "state recapture" in p.fixedPointResidual
    assert p.fixedPointResidual["state recapture"]["abs_sum"] < 50.0


def test_cash_flow_balance_includes_the_recapture():
    p = _plan([14000, 8000])
    assert p.st_T_n[1] == pytest.approx(np.sum(p.st_T_tn[:, 1]) + p.st_recap_n[1])


def test_yonkers_surcharge_applies_to_the_recapture_too():
    p = _plan([14000, 8000], locality="Yonkers")
    state = np.sum(p.st_T_tn, axis=0) + p.st_recap_n
    np.testing.assert_allclose(p.lt_T_n, 0.1675 * state, rtol=1e-9)
    assert p.st_recap_n[1] > 1000


def test_no_recapture_outside_new_york_or_after_leaving():
    nj = _plan([14000, 8000], state="NJ")
    assert not nj._str_active and np.all(nj.st_recap_n == 0)
    moved = _plan([14000, 8000], moves=[(2031, "FL")])
    assert np.all(moved.st_recap_n[1:5] > 0) and np.all(moved.st_recap_n[5:] == 0)


def test_summary_breaks_out_recapture_and_local_tax():
    from owlplanner.export import build_summary_dic

    labels = " ".join(build_summary_dic(_plan([14000, 8000], locality="Yonkers")))
    assert "Total state benefit recapture paid" in labels and "Total local income tax paid" in labels
    labels = " ".join(build_summary_dic(_plan([14000, 8000], state="NJ")))
    assert "recapture" not in labels and "local income tax" not in labels


def test_replayed_rows_match_a_fresh_build_with_recapture_local_tax_and_a_move():
    """The loop-invariant builders are replayed after the first iteration (upstream #151). None of them may
    read what recapture, local tax or a move changes; compare a replayed build with a fresh one."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "fixed_rows", Path(__file__).parents[1] / "solver" / "test_fixed_rows.py"
    )
    fr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fr)

    p = _plan([14000, 8000], moves=[(2031, "NY", "NYC"), (2036, "NJ")], locality="Yonkers")
    assert p.st_recap_n.sum() > 0 and p.lt_T_n.sum() > 0
    assert p._fixedRows
    p._buildConstraints(p.objective, p.solverOptions)
    replayed = fr._lp_arrays(p)
    p._fixedRows = {}
    p._buildConstraints(p.objective, p.solverOptions)
    fr._assert_same_lp(fr._lp_arrays(p), replayed)
