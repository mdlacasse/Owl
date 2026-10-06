"""Local (city and county) income tax on top of the state's."""

from datetime import date

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import tax_local
from owlplanner.config import config_to_plan, plan_to_config

THISYEAR = date.today().year
GAMMA = np.array([1.025**n for n in range(31)])

_FLAT = """
["XX:Flat"]
description = "flat 3% above a $10,000 threshold"
type = "brackets"
base = "state_taxable"
brackets = [[0.0, 0.0], [10000.0, 3.0]]
"""


def _write(tmp_path, text, name="local.toml"):
    f = tmp_path / name  # the loader caches by path, so variants need distinct names
    f.write_text(text, encoding="utf-8")
    return str(f)


# ---------------------------------------------------------------------------
# Data and parameters
# ---------------------------------------------------------------------------


def test_new_york_localities():
    assert tax_local.valid_localities("NY") == ["NYC", "Yonkers"]
    assert tax_local.valid_localities("ny") == ["NYC", "Yonkers"]
    assert tax_local.valid_localities("CA") == []


def test_canonical_locality_ignores_case_and_rejects_unknown():
    assert tax_local.canonical_locality("NY", " yonkers ") == "Yonkers"
    assert tax_local.canonical_locality("NY", "") == ""
    with pytest.raises(ValueError, match="Unknown locality"):
        tax_local.canonical_locality("NY", "Albany")


def test_nyc_brackets_switch_to_single_at_n_d():
    p = tax_local.local_taxParams("NY", "NYC", 2, 10, 30, GAMMA)
    assert p.N_lt == 4
    np.testing.assert_allclose(p.theta_tn[:, 0], [0.03078, 0.03762, 0.03819, 0.03876])
    np.testing.assert_array_equal(p.theta_tn[:, 0], p.theta_tn[:, 20])
    assert p.DeltaBar_tn[0, 0] == 21600 and p.DeltaBar_tn[0, 20] == 12000
    assert np.all(p.surcharge_n == 0)


def test_nyc_thresholds_are_not_indexed_but_the_top_bracket_keeps_room():
    p = tax_local.local_taxParams("NY", "NYC", 2, 30, 30, GAMMA)
    np.testing.assert_array_equal(p.DeltaBar_tn[:3, 0], p.DeltaBar_tn[:3, 29])
    assert p.DeltaBar_tn[3, 29] == pytest.approx(5_000_000 * GAMMA[29])


def test_yonkers_is_a_surcharge_with_no_brackets():
    p = tax_local.local_taxParams("NY", "Yonkers", 2, 30, 30, GAMMA)
    assert p.N_lt == 0
    np.testing.assert_allclose(p.surcharge_n, 0.1675)


def test_flat_rate_with_threshold_is_two_brackets(tmp_path):
    f = _write(tmp_path, _FLAT)
    p = tax_local.local_taxParams("XX", "Flat", 1, 30, 30, np.ones(31), toml_path=f)
    assert p.N_lt == 2
    np.testing.assert_allclose(p.theta_tn[:, 0], [0.0, 0.03])
    assert p.DeltaBar_tn[0, 0] == 10000


def test_bad_type_or_base_is_rejected(tmp_path):
    bad_type = _write(tmp_path, _FLAT.replace('"brackets"\nbase', '"graduated"\nbase'), "type.toml")
    with pytest.raises(ValueError, match="type must be"):
        tax_local.local_taxParams("XX", "Flat", 1, 30, 30, np.ones(31), toml_path=bad_type)
    bad_base = _write(tmp_path, _FLAT.replace("state_taxable", "wages"), "base.toml")
    with pytest.raises(ValueError, match="has base"):
        tax_local.local_taxParams("XX", "Flat", 1, 30, 30, np.ones(31), toml_path=bad_base)


def test_schedule_follows_the_locality_in_force():
    res = [("NY", "NYC")] * 5 + [("NY", "Yonkers")] * 5 + [("FL", "")] * 20
    p = tax_local.local_taxParams_schedule(res, 2, 30, 30, GAMMA)
    assert p.N_lt == 4
    assert np.all(p.theta_tn[:, :5].max(axis=0) > 0) and np.all(p.theta_tn[:, 5:] == 0)
    assert np.all(p.surcharge_n[:5] == 0) and np.all(p.surcharge_n[5:10] == 0.1675) and np.all(p.surcharge_n[10:] == 0)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _plan(locality="", state="NY", moves=()):
    """A couple whose income is fixed (pensions and Social Security), so the tax is not a choice.

    Solved for the largest bequest at a fixed spending: every dollar of tax then costs bequest in
    every year. Under maxSpending the first year's income alone can cap spending, leaving later
    years' tax free and the optimizer indifferent to it.
    """
    p = owl.Plan(["Joe", "Jane"], ["1964-06-15", "1964-12-15"], [85, 85], "Local")
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[0, 0], taxDeferred=[0, 0], taxFree=[0, 0])
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
    p.setRates("conservative")
    p.setSocialSecurity([2800, 2200], [70, 70])
    p.setPension([6000, 3000], [62, 62], [False, False])
    p.setStateTax(state, moves, locality)
    return p


def _solve(p):
    options = {"noRothConversions": "None", "maxRothConversion": 0, "withMedicare": "None", "netSpending": 35}
    p.solve("maxBequest", options=options)
    assert p.caseStatus == "solved"
    return p


def _apply_brackets(brackets, income):
    tax = 0.0
    for k, (lo, rate) in enumerate(brackets):
        hi = brackets[k + 1][0] if k + 1 < len(brackets) else np.inf
        tax += max(0.0, min(income, hi) - lo) * rate / 100
    return tax


def test_hand_computed_nyc_tax():
    """$100,000 of NYC taxable income, married: 21,600 at 3.078%, 23,400 at 3.762%, 45,000 at 3.819%, rest at 3.876%."""
    expected = 21600 * 0.03078 + 23400 * 0.03762 + 45000 * 0.03819 + 10000 * 0.03876
    assert expected == pytest.approx(3651.31, abs=0.01)
    schedule = [(0, 3.078), (21600, 3.762), (45000, 3.819), (90000, 3.876)]
    assert _apply_brackets(schedule, 100_000) == pytest.approx(expected)


def test_yonkers_is_16_75_percent_of_the_state_tax():
    plain = _solve(_plan())
    yonkers = _solve(_plan("Yonkers"))
    assert plain.st_T_n.sum() > 10_000, "test needs a real state tax"
    assert np.all(plain.lt_T_n == 0)
    net_state = np.sum(yonkers.st_T_tn, axis=0) + yonkers.st_recap_n  # the surcharge base includes recapture
    np.testing.assert_allclose(yonkers.lt_T_n, 0.1675 * net_state, rtol=1e-9)
    np.testing.assert_allclose(yonkers.st_T_n, 1.1675 * net_state, rtol=1e-9)
    # The surcharge also nudges the optimum, so against the plain plan only the size is comparable.
    assert yonkers.st_T_n.sum() == pytest.approx(1.1675 * plain.st_T_n.sum(), rel=0.05)


def test_nyc_tax_is_the_schedule_applied_to_state_taxable_income():
    p = _solve(_plan("NYC"))
    base = np.sum(p.st_f_tn, axis=0)
    assert base.max() > 90_000, "test needs income in the top NYC bracket"
    for n in range(p.N_n):
        sched = (
            [(0, 3.078), (21600, 3.762), (45000, 3.819), (90000, 3.876)]
            if n < p.n_d
            else [(0, 3.078), (12000, 3.762), (25000, 3.819), (50000, 3.876)]
        )
        assert p.lt_T_n[n] == pytest.approx(_apply_brackets(sched, base[n]), abs=0.5)
    np.testing.assert_allclose(p.st_T_n - p.lt_T_n, np.sum(p.st_T_tn, axis=0) + p.st_recap_n, rtol=1e-9)


def test_locality_adds_to_the_total_and_cash_flow_still_balances():
    p = _solve(_plan("NYC"))
    assert p.lt_T_n.sum() > 0
    assert p.st_T_n.sum() == pytest.approx(np.sum(p.st_T_tn) + p.st_recap_n.sum() + p.lt_T_n.sum())


def test_locality_lowers_spending():
    plain = _solve(_plan()).bequest
    assert _solve(_plan("NYC")).bequest < plain
    assert _solve(_plan("Yonkers")).bequest < plain


def test_rest_of_westchester_is_plain_new_york():
    assert _solve(_plan("")).bequest == pytest.approx(_solve(_plan()).bequest)


def test_local_tax_stops_when_moving_away():
    p = _solve(_plan("NYC", moves=[(THISYEAR + 4, "NJ")]))
    assert p.lt_T_n[:4].sum() > 0 and np.all(p.lt_T_n[4:] == 0)


def test_moving_into_a_locality():
    p = _solve(_plan("", moves=[(THISYEAR + 4, "NY", "Yonkers")]))
    assert np.all(p.lt_T_n[:4] == 0) and p.lt_T_n[4:].sum() > 0


def test_bad_locality_raises():
    p = _plan()
    with pytest.raises(ValueError, match="Unknown locality"):
        p.setStateTax("NY", locality="Albany")
    with pytest.raises(ValueError, match="Unknown locality"):
        p.setStateTax("NJ", locality="NYC")
    assert p.locality == ""


def test_config_round_trip_keeps_the_locality():
    p = _plan("Yonkers", moves=[(THISYEAR + 5, "NY", "NYC")])
    conf = plan_to_config(p)
    assert conf["basic_info"]["locality"] == "Yonkers"
    assert conf["basic_info"]["moves"] == [{"year": THISYEAR + 5, "state": "NY", "locality": "NYC"}]
    q = config_to_plan(conf)
    assert q.locality == "Yonkers" and q.state_moves == p.state_moves
