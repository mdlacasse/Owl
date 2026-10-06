"""Changing state of residence during the plan."""

from datetime import date

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import residency, tax_state
from owlplanner.config import config_to_plan, plan_to_config

THISYEAR = date.today().year
GAMMA = np.array([1.025**n for n in range(31)])


def _params(states_n, **kw):
    return tax_state.st_schedule(states_n, 2, 30, 30, GAMMA, [1964, 1964], mobs=[6, 12], **kw)


# ---------------------------------------------------------------------------
# residence_by_year
# ---------------------------------------------------------------------------


def _states(state, moves, N_n, locality=""):
    return [s for s, _ in residency.residence_by_year(state, locality, moves, THISYEAR, N_n)]


def test_residence_by_year_applies_moves_in_order():
    got = _states("ny", [(THISYEAR + 8, "nj"), (THISYEAR + 3, "FL")], 12)
    assert got == ["NY"] * 3 + ["FL"] * 5 + ["NJ"] * 4


def test_residence_by_year_without_moves_is_constant():
    assert _states("MN", (), 5) == ["MN"] * 5
    assert _states("", (), 5) == [""] * 5


def test_residence_by_year_can_start_with_no_state():
    assert _states("", [(THISYEAR + 2, "NY")], 4) == ["", "", "NY", "NY"]


def test_locality_does_not_survive_a_move_to_another_state():
    got = residency.residence_by_year("NY", "NYC", [(THISYEAR + 2, "NJ")], THISYEAR, 4)
    assert got == [("NY", "NYC")] * 2 + [("NJ", "")] * 2


def test_a_move_can_name_a_locality():
    got = residency.residence_by_year("NY", "NYC", [(THISYEAR + 2, "NY", "yonkers")], THISYEAR, 4)
    assert got == [("NY", "NYC")] * 2 + [("NY", "Yonkers")] * 2


@pytest.mark.parametrize(
    "move,msg",
    [
        ((THISYEAR, "FL"), "after the first plan year"),
        ((THISYEAR + 5, "FL"), "within the plan"),
        ((THISYEAR + 2, "ZZ"), "Unknown state"),
        ((THISYEAR + 2, "FL", "NYC"), "Unknown locality"),
    ],
)
def test_residence_by_year_rejects_bad_moves(move, msg):
    with pytest.raises(ValueError, match=msg):
        residency.residence_by_year("NY", "", [move], THISYEAR, 5)


def test_residence_by_year_rejects_two_moves_in_one_year():
    with pytest.raises(ValueError, match="Two moves"):
        residency.residence_by_year("NY", "", [(THISYEAR + 2, "FL"), (THISYEAR + 2, "NJ")], THISYEAR, 5)


def test_locality_needs_a_state():
    with pytest.raises(ValueError, match="needs a state"):
        residency.normalize("", "NYC")


# ---------------------------------------------------------------------------
# st_schedule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("state", ["NY", "NJ", "CO", "FL", "PA"])
def test_constant_schedule_matches_single_state(state):
    single = tax_state.st_taxParams(state, 2, 30, 30, GAMMA, [1964, 1964], mobs=[6, 12])
    sched = _params([state] * 30)
    assert sched.N_st == single.N_st
    for name in single.__dataclass_fields__:
        np.testing.assert_array_equal(getattr(sched, name), getattr(single, name), err_msg=name)


def test_columns_follow_the_state_in_force():
    ny = tax_state.st_taxParams("NY", 2, 30, 30, GAMMA, [1964, 1964], mobs=[6, 12])
    fl = tax_state.st_taxParams("FL", 2, 30, 30, GAMMA, [1964, 1964], mobs=[6, 12])
    sched = _params(["NY"] * 10 + ["FL"] * 20)
    np.testing.assert_array_equal(sched.theta_tn[: ny.N_st, :10], ny.theta_tn[:, :10])
    np.testing.assert_array_equal(sched.theta_tn[:, 10:], fl.theta_tn[:1, 10:].repeat(sched.N_st, axis=0))
    np.testing.assert_array_equal(sched.re_cap_in[:, 10:], fl.re_cap_in[:, 10:])
    np.testing.assert_array_equal(sched.re_cap_in[:, :10], ny.re_cap_in[:, :10])
    assert sched.sigmaBar_n[9] == ny.sigmaBar_n[9] and sched.sigmaBar_n[10] == fl.sigmaBar_n[10]
    assert np.all(sched.sigmaBar_n[:10] == ny.sigmaBar_n[0])  # NY's deduction is fixed in statute


def test_state_free_years_take_no_tax():
    sched = _params([""] * 5 + ["NY"] * 25)
    assert np.all(sched.theta_tn[:, :5] == 0)
    assert sched.DeltaBar_tn[0, 0] > 1e6  # room for any income at 0%
    assert np.all(sched.theta_tn[:, 5:].max(axis=0) > 0)


def test_mixed_bracket_counts_pad_with_zero_width_top_rate():
    """MN has 4 brackets and NJ 8: MN years get NJ-sized arrays that still tax the top at MN's top rate."""
    mn = tax_state.st_taxParams("MN", 2, 30, 30, GAMMA, [1964, 1964], mobs=[6, 12])
    sched = _params(["MN"] * 15 + ["NJ"] * 15)
    assert sched.N_st == 8 > mn.N_st
    assert np.all(sched.theta_tn[mn.N_st :, 0] == mn.theta_tn[-1, 0])
    assert np.all(sched.DeltaBar_tn[mn.N_st :, 0] == 0)
    assert sched.DeltaBar_tn[mn.N_st - 1, 0] == mn.DeltaBar_tn[-1, 0]


def test_flags_follow_the_state_in_force():
    """MD does not count conversions; IL exempts retirement income; both vary by year."""
    sched = _params(["MD"] * 10 + ["IL"] * 20)
    assert not sched.conv_ok_n[:10].any() and sched.conv_ok_n[10:].all()


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _plan(state, moves=()):
    p = owl.Plan(["Joe", "Jane"], ["1964-06-15", "1964-12-15"], [85, 85], "Residency")
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100, 0], taxDeferred=[900, 300], taxFree=[50, 50])
    p.setAllocationRatios("individual", generic=np.array([[[60, 40, 0, 0], [60, 40, 0, 0]]] * 2))
    p.setRates("conservative")
    p.setSocialSecurity([2800, 2200], [70, 70])
    p.setStateTax(state, moves)
    return p


def _solve(p):
    p.solve("maxSpending", options={"noRothConversions": "None", "maxRothConversion": 0, "withMedicare": "None"})
    assert p.caseStatus == "solved"
    return p


def test_setStateTax_validates_moves():
    p = _plan("NY")
    with pytest.raises(ValueError, match="Unknown state"):
        p.setStateTax("NY", [(THISYEAR + 3, "QQ")])
    with pytest.raises(ValueError, match="after the first plan year"):
        p.setStateTax("NY", [(THISYEAR, "FL")])
    assert p.state == "NY" and p.state_moves == []  # rejected calls leave the plan untouched


def test_setStateTax_without_moves_resets_them():
    p = _plan("NY", [(THISYEAR + 3, "FL")])
    p.setStateTax("NY")
    assert p.state_moves == []


def test_no_state_tax_after_moving_to_florida():
    p = _solve(_plan("NY", [(THISYEAR + 4, "FL")]))
    assert np.all(p.st_T_n[:4] > 0)
    assert np.all(p.st_T_n[4:] == 0)


def test_state_tax_only_after_moving_in():
    p = _solve(_plan("", [(THISYEAR + 4, "NY")]))
    assert np.all(p.st_T_n[:4] == 0)
    assert p.st_T_n[4:].sum() > 0


def test_moving_earlier_never_lowers_spending():
    stay = _solve(_plan("NY"))
    late = _solve(_plan("NY", [(THISYEAR + 10, "FL")]))
    early = _solve(_plan("NY", [(THISYEAR + 2, "FL")]))
    assert stay.basis <= late.basis + 1e-6 <= early.basis + 2e-6
    assert late.basis > stay.basis


def test_move_year_is_billed_by_the_destination():
    """A move in year k means year k already belongs to the new state."""
    p = _solve(_plan("NY", [(THISYEAR + 4, "FL")]))
    assert p.st_T_n[3] > 0 and p.st_T_n[4] == 0


def test_config_round_trip_keeps_moves():
    p = _plan("NY", [(THISYEAR + 4, "FL"), (THISYEAR + 9, "NJ")])
    conf = plan_to_config(p)
    assert conf["basic_info"]["moves"] == [{"year": THISYEAR + 4, "state": "FL"}, {"year": THISYEAR + 9, "state": "NJ"}]
    assert "locality" not in conf["basic_info"]
    q = config_to_plan(conf)
    assert q.state == "NY" and q.state_moves == p.state_moves


def test_config_without_moves_writes_none():
    assert "moves" not in plan_to_config(_plan("NY"))["basic_info"]


def test_config_rejects_a_bad_move():
    conf = plan_to_config(_plan("NY"))
    conf["basic_info"]["moves"] = [{"year": THISYEAR + 3, "state": "QQ"}]
    with pytest.raises(ValueError, match="Invalid state in config"):
        config_to_plan(conf)
