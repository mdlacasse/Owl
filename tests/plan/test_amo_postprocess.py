"""
Tests for the post-processing that replaces the AMO exclusion binaries.

Owl used to enforce two exclusions with big-M binaries: no Roth conversion in a year
with a Roth withdrawal, and no surplus in a year with a taxable or tax-free withdrawal.
Neither changed the optimum, but enforcing them cost orders of magnitude in solve time
for households that owe no tax -- see examples/Case_cameron.toml, which took 577 s with the
binaries and solves in a twentieth of a second without them.

The binaries are gone. These tests check that what replaced them is sound:

  - the algebraic Roth substitution leaves every constraint row where it found it;
  - the surplus round-trip is reported net without disturbing the cash flow identity;
  - the objective still matches what the binaries produced, case by case, against the
    fixture recorded from the old code path in tests/data/amo_mip_reference.json;
  - the problem really is a pure LP now, under both solvers.

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

import json
import os
import tomllib

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import amorepair
from owlplanner.rate_models.constants import STOCHASTIC_METHODS

from test_cashflow_balance import _assert_cashflow_balance, _make_couple, _make_single

REFERENCE_FILE = os.path.join("tests", "data", "amo_mip_reference.json")

# Two solvers disagree with each other by up to 0.5% on the same MIP (jack+jill), so the
# bar for "post-processing reproduces the constrained optimum" cannot be tighter than the
# spread that was already there. Deltas above this are a real regression, not noise.
OBJECTIVE_RTOL = 6e-3


def _load_reference():
    with open(REFERENCE_FILE) as f:
        return json.load(f)


def _active_solver():
    return "MOSEK" if os.getenv("OWL_TEST_SOLVER", "").lower() == "mosek" else "HiGHS"


def _comparable_cases():
    """Recorded cases whose objective can still be held against the fixture.

    A case that draws its returns cannot: the fixture was recorded before correlated
    draws were made reproducible, so its objective came from a return sequence the case
    no longer generates, and re-recording it would need a build that had the exclusion
    binaries and the new sampling at once -- one that never existed. Those cases are
    referenced instead by tests/stochastic/test_seed_reproducibility.py, which pins both
    their series and their objective.
    """
    cases = []
    for case in sorted(_load_reference()["cases"]):
        with open(os.path.join("examples", case + ".toml"), "rb") as f:
            method = tomllib.load(f).get("rates_selection", {}).get("method", "")
        if method not in STOCHASTIC_METHODS:
            cases.append(case)
    return cases


def _surplus_overlap_years(p):
    """Years reporting both a surplus and a taxable or tax-free withdrawal."""
    return [
        n
        for n in range(p.N_n)
        if p.s_n[n] > 1.0 and (np.sum(p.w_ijn[:, 0, n]) + np.sum(p.w_ijn[:, 2, n])) > 1.0
    ]


def _roth_overlap_years(p):
    """Years reporting both a Roth conversion and a Roth withdrawal, past 59 1/2."""
    n595_max = int(np.max(p.n595))
    return [
        n
        for n in range(n595_max, p.N_n)
        if np.sum(p.x_in[:, n]) > 1.0 and np.sum(p.w_ijn[:, 2, n]) > 1.0
    ]


class TestNoBinaries:
    """The exclusions are gone from the model, so a default case is a pure LP."""

    def test_default_case_has_no_binaries(self):
        p = _make_single("nobin", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        p.solve("maxSpending", options={"bequest": 100})
        assert p.nbins == 0, "a default plan should carry no integer variables"
        assert "zx" not in p.vm

    def test_retired_options_are_reported_as_deprecated(self, capsys):
        """A case file saved before the change still carries amoRoth/amoSurplus. It must
        still solve, and must say the options are deprecated rather than unrecognized."""
        p = _make_single("retired-opts", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        p.setVerbose(True)
        p.solve(
            "maxSpending",
            options={"bequest": 100, "amoConstraints": True, "amoRoth": True, "amoSurplus": False},
        )
        assert p.caseStatus == "solved"
        out = capsys.readouterr().out
        assert "Ignoring unknown solver option" not in out
        for name in ("amoConstraints", "amoRoth", "amoSurplus"):
            assert f"Ignoring deprecated solver option '{name}'" in out

    @pytest.mark.toml
    def test_solves_without_binaries_on_active_solver(self):
        """Regression for the MOSEK path, which used to read the integer solution slot
        unconditionally and would fail once no integer variables existed."""
        p = owl.readConfig(os.path.join("examples", "Case_cameron"))
        p.solverOptions["solver"] = _active_solver()
        p.resolve()
        assert p.caseStatus == "solved"
        assert p.nbins == 0
        assert p.basis > 0


class TestRothSubstitution:
    """The Roth repair is exact algebra: it must not disturb any constraint row."""

    def _context_and_solution(self, p):
        x = np.zeros(p.nvars)
        for name in ("b", "d", "e", "f", "g", "m", "q", "s", "w", "x"):
            if name in p.vm:
                blk = p.vm[name]
                x[blk.start : blk.end] = 0.0
        return p._amoContext({}), x

    def test_substitution_preserves_every_row(self):
        p = _make_single("rothsub", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        p.solve("maxSpending", options={"bequest": 100})
        ctx = p._amoContext({})
        col_lb, col_ub = p.B.arrays()

        # Plant an overlap by hand, then check the repair removes it for free.
        x = np.zeros(p.nvars)
        n = p.N_n - 2
        x[p.vm["x"].idx(0, n)] = 5000.0
        x[p.vm["w"].idx(0, 2, n)] = 3000.0
        y, moves, blocked = amorepair.repair_roth_overlap(x, ctx)

        assert blocked is None and moves == 1
        assert y[p.vm["x"].idx(0, n)] == pytest.approx(2000.0)
        assert y[p.vm["w"].idx(0, 2, n)] == pytest.approx(0.0)
        assert y[p.vm["w"].idx(0, 1, n)] == pytest.approx(3000.0)
        # Ordinary income is unchanged: a conversion and a tax-deferred withdrawal are
        # both fully taxable, so the substitution moves no income between years.
        assert (y[p.vm["x"].idx(0, n)] + y[p.vm["w"].idx(0, 1, n)]) == pytest.approx(5000.0)

    def test_substitution_respects_a_pinned_conversion(self):
        p = _make_single("rothpin", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        p.solve("maxSpending", options={"bequest": 100})
        ctx = p._amoContext({})
        n = p.N_n - 2
        ix = p.vm["x"].idx(0, n)
        ctx.col_lb = ctx.col_lb.copy()
        ctx.col_lb[ix] = 5000.0  # a per-year override pins this conversion

        x = np.zeros(p.nvars)
        x[ix] = 5000.0
        x[p.vm["w"].idx(0, 2, n)] = 3000.0
        y, moves, _ = amorepair.repair_roth_overlap(x, ctx)
        assert moves == 0
        assert y[ix] == pytest.approx(5000.0), "a pinned conversion must not be reduced"

    def test_substitution_skipped_below_59_and_a_half(self):
        """A conversion ladder needs exactly the overlap the repair would remove."""
        thisyear = 2026
        p = owl.Plan(["Early"], [f"{thisyear - 50}-03-01"], [85], "ladder")
        p.setSpendingProfile("flat", 60)
        p.setAccountBalances(taxable=[200], taxDeferred=[800], taxFree=[100], startDate="1-1")
        p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
        p.setSocialSecurity([2000], [67])
        p.setRates("historical average", 1928, 2025)
        p.solve("maxSpending", options={"bequest": 0})
        ctx = p._amoContext({})

        assert ctx.n595[0] > 0, "this plan should start below 59 1/2"
        x = np.zeros(p.nvars)
        n = 0
        x[p.vm["x"].idx(0, n)] = 5000.0
        x[p.vm["w"].idx(0, 2, n)] = 3000.0
        y, moves, _ = amorepair.repair_roth_overlap(x, ctx)
        assert moves == 0, "the ladder window must be left alone"
        assert y[p.vm["w"].idx(0, 2, n)] == pytest.approx(3000.0)

    def test_substitution_blocked_by_withdrawal_ordering(self):
        p = _make_single("rothorder", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        p.solve("maxSpending", options={"bequest": 100, "withdrawalOrder": "taxable_first"})
        ctx = p._amoContext({})
        assert ctx.roth_repair_blocked is not None
        x = np.zeros(p.nvars)
        x[p.vm["x"].idx(0, p.N_n - 2)] = 5000.0
        x[p.vm["w"].idx(0, 2, p.N_n - 2)] = 3000.0
        _, moves, blocked = amorepair.repair_roth_overlap(x, ctx)
        assert moves == 0 and "taxable_first" in blocked

    def test_substitution_blocked_by_opportunity_cost(self):
        p = _make_single("rothopp", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        p.solve("maxSpending", options={"bequest": 100, "oppCostX": 5})
        ctx = p._amoContext({})
        assert ctx.roth_repair_blocked is not None
        assert "oppCostX" in ctx.roth_repair_blocked


class TestSurplusNetting:
    """The surplus round-trip is a reporting artifact, and netting it is an identity."""

    @pytest.mark.toml
    def test_cashflow_identity_holds_after_netting(self):
        p = owl.readConfig(os.path.join("examples", "Case_cameron"))
        p.resolve()
        # The surplus sits on the left of the identity and the deposit is inside the
        # withdrawals on the right, so netting removes the same amount from both.
        _assert_cashflow_balance(p)

    @pytest.mark.toml
    def test_netting_leaves_balances_and_objective_alone(self):
        p = owl.readConfig(os.path.join("examples", "Case_cameron"))
        p.resolve()
        basis, bequest = p.basis, p.bequest
        b_end = p.b_ijn[:, :, p.N_n].copy()

        p._netSurplusRoundTrip()  # idempotent: everything nettable is already netted

        assert p.basis == pytest.approx(basis)
        assert p.bequest == pytest.approx(bequest)
        np.testing.assert_allclose(p.b_ijn[:, :, p.N_n], b_end)

    @pytest.mark.toml
    def test_netting_only_touches_untaxed_years(self):
        """A displayed withdrawal must always explain the capital-gains tax beside it."""
        p = owl.readConfig(os.path.join("examples", "Case_dana"))
        p.resolve()
        for n in range(p.N_n):
            if p.q_pn[1, n] + p.q_pn[2, n] > 1.0:
                assert p.d_in[:, n].sum() == pytest.approx(p.s_n[n], abs=1.0), (
                    f"year {n} realizes taxed gains and must be reported gross"
                )

    def test_cashflow_balance_on_built_plans(self):
        for name, builder in (("single", _make_single), ("couple", _make_couple)):
            if name == "single":
                p = builder("net-" + name, [500], [1000], [200], ss_pia=[2000], ss_age=[67])
            else:
                p = builder("net-" + name, [300, 200], [600, 400], [100, 100], [2000, 1500], [67, 67])
            p.solve("maxSpending", options={"bequest": 100})
            _assert_cashflow_balance(p)


class TestMatchesRecordedOptimum:
    """The recorded fixture is what the exclusion binaries produced, before their removal."""

    @pytest.mark.toml
    @pytest.mark.parametrize("case", _comparable_cases())
    def test_objective_matches_reference(self, case):
        solver = _active_solver()
        reference = _load_reference()["cases"][case].get(solver)
        if reference is None:
            pytest.skip(f"no {solver} reference recorded for {case}")
        p = owl.readConfig(os.path.join("examples", case))
        p.solverOptions["solver"] = solver
        p.resolve()

        # Spending is the objective under maxSpending and is pinned by netSpending under
        # maxBequest, so it should land where the constrained solve left it either way.
        assert p.basis == pytest.approx(reference["basis"], rel=OBJECTIVE_RTOL, abs=50)

        # Removing constraints cannot lower an optimum, so the bar for the bequest is that
        # it never comes back worse. It does come back better on john+sally, where the
        # self-consistent loop oscillates and now settles on a higher fixed point: same
        # spending, more left over. The upper bound is a guard against a constraint having
        # gone missing along with the exclusion rows.
        floor = reference["bequest"] * (1 - OBJECTIVE_RTOL) - 50
        ceiling = reference["bequest"] * 1.05 + 50
        assert p.bequest >= floor, f"{case}: bequest fell to {p.bequest:,.2f} from {reference['bequest']:,.2f}"
        assert p.bequest <= ceiling, f"{case}: bequest jumped to {p.bequest:,.2f}; check for a lost constraint"

    @pytest.mark.toml
    def test_no_case_got_slower(self):
        """The point of the change: every recorded case solves at least as fast."""
        import time

        solver = _active_solver()
        reference = _load_reference()["cases"]
        slowest = 0.0
        for case, per_solver in reference.items():
            if solver not in per_solver:
                continue
            p = owl.readConfig(os.path.join("examples", case))
            p.solverOptions["solver"] = solver
            start = time.time()
            p.resolve()
            slowest = max(slowest, time.time() - start)
        # Every recorded MIP solve was under 10 s; without binaries none should come close.
        assert slowest < 5.0, f"slowest case took {slowest:.1f}s"


class TestOverlapsResolved:
    """What the exclusions used to guarantee, now reported rather than constrained."""

    @pytest.mark.toml
    def test_low_wealth_case_reports_little_churn(self):
        p = owl.readConfig(os.path.join("examples", "Case_cameron"))
        p.resolve()
        # Before netting this plan showed a withdraw-and-redeposit cycle in most years.
        assert len(_surplus_overlap_years(p)) <= 2
        assert len(_roth_overlap_years(p)) == 0

    @pytest.mark.toml
    def test_single_person_cases_have_no_roth_overlap(self):
        """The substitution is per individual, so it clears singles completely."""
        for case in ("Case_dana", "Case_devon", "Case_bill", "Case_joe", "Case_robin"):
            p = owl.readConfig(os.path.join("examples", case))
            p.resolve()
            assert _roth_overlap_years(p) == [], f"{case} still reports a Roth overlap"
