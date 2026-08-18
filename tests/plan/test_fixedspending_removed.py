"""
Tests for the withdrawal of the fixedSpending solver option.

fixedSpending pinned g(0), and with the default spendingSlack of zero the spending-profile
rows tie every g(n) to g(0). That left the maxSpending objective, which is built only from
g(n) coefficients, constant over the entire feasible set. The ordinary-tax model is a
bracket-fill relaxation that is tight only because the objective pushes income into the
cheapest brackets, so with nothing left to push, the solver was free to fill the 37% bracket
while lower ones sat empty. The wasted money was absorbed by the estate at no cost to the
objective, the bequest floor being one dollar by default. Reported as issue #140, where one
year charged 46.7% on $292k of ordinary income.

The option is rejected rather than ignored: a case file that asks for a pinned spending
level would otherwise solve as an ordinary unconstrained maxSpending without saying so.
These tests check that both doors are closed -- the solver call and the config load -- and
that the replacement, a swept bequest floor, taxes correctly at the same spending level.

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

from owlplanner.config.schema import REMOVED_OPTIONS, parse_solver_options

from test_cashflow_balance import _make_single


class TestOptionRejected:
    def test_solve_raises(self):
        """Plan.solve() refuses the option outright rather than ignoring it."""
        p = _make_single("removed-opt", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        with pytest.raises(ValueError, match="fixedSpending.*has been removed"):
            p.solve("maxSpending", options={"bequest": 100, "fixedSpending": 40})

    def test_config_load_raises(self):
        """A case file carrying the option fails at load, not silently at solve time."""
        with pytest.raises(ValueError, match="fixedSpending.*has been removed"):
            parse_solver_options({"bequest": 100.0, "fixedSpending": 40.0, "units": "k"})

    def test_reason_points_at_the_replacement(self):
        """The message has to tell a reader what to use instead."""
        reason = REMOVED_OPTIONS["fixedSpending"]
        assert "#140" in reason
        assert "frontier" in reason

    def test_unaffected_options_still_load(self):
        """Rejection is keyed on the one name; neighbouring options are untouched."""
        out = parse_solver_options({"bequest": 100.0, "netSpending": 40.0, "units": "k"})
        assert out["bequest"] == 100.0
        assert out["netSpending"] == 40.0


class TestReplacementTaxesCorrectly:
    """The bequest floor is the replacement knob, and it keeps the objective non-degenerate."""

    def test_pinned_spending_level_taxes_below_top_rate(self):
        """
        Issue #140's symptom, at a spending level the plan can more than afford.

        Reaching that level through the bequest objective leaves g(0) free, so the
        objective keeps its teeth and the bracket variables stay priced.
        """
        p = _make_single("frontier-pt", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
        p.solve("maxBequest", options={"netSpending": 40})
        assert p.caseStatus == "solved"

        G = np.asarray(p.G_n, float)
        T = np.asarray(p.T_n, float)
        rates = [T[i] / G[i] for i in range(len(G)) if G[i] > 1]
        assert rates, "case should have at least one year of ordinary income"
        # No progressive schedule can charge more than the top statutory marginal rate.
        assert max(rates) <= 0.37 + 1e-9, f"effective ordinary rate {max(rates):.4f} exceeds the top bracket"

    def test_raising_the_bequest_floor_costs_spending(self):
        """
        The frontier is a real trade-off: a higher floor must not buy more spending.

        This is the property that makes each point an optimum rather than an arbitrary
        vertex, which is exactly what the pinned objective lost.
        """
        bases = []
        for bequest in (0, 200, 400):
            p = _make_single(f"floor-{bequest}", [500], [1000], [200], ss_pia=[2000], ss_age=[67])
            p.solve("maxSpending", options={"bequest": bequest})
            assert p.caseStatus == "solved"
            bases.append(p.basis)

        for lo, hi in zip(bases, bases[1:]):
            assert hi <= lo + 1e-6, f"spending rose from {lo:.2f} to {hi:.2f} as the bequest floor increased"
