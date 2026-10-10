"""
Tests for the branch-and-bound node reporting (solverNodes, solverNodesTotal, solverNodeLimitHits) and the
mipMaxNodes solver option.

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

import owlplanner as owl
from owlplanner import localsearch
from owlplanner.export import _local_search_step_limit
from owlplanner.plan import HIGHS_MAX_NODES, Plan

NODES_ROW = "MIP nodes (accepted solution / whole solve)"
LIMIT_ROW = "MIP node limit"


def _plan():
    p = owl.Plan(["Sam"], ["1976-04-10"], [70], "nodes", verbose=False)
    p.setAccountBalances(taxable=[3600], taxDeferred=[580], taxFree=[720])
    p.setCostBasis([1380])
    p.setSocialSecurity([3700], [70])
    p.setAllocationRatios(
        "account",
        taxable=[[[94, 0, 6, 0], [94, 0, 6, 0]]],
        taxDeferred=[[[0, 0, 100, 0], [0, 0, 100, 0]]],
        taxFree=[[[0, 0, 100, 0], [0, 0, 100, 0]]],
    )
    p.setSpendingProfile("flat")
    p.setRates("historical", frm=1969)
    return p


def test_node_limit_defaults_and_option():
    assert Plan._mipNodeLimit({}, mosek=False) == HIGHS_MAX_NODES
    assert Plan._mipNodeLimit({}, mosek=True) == -1
    assert Plan._mipNodeLimit({"mipMaxNodes": 500}, mosek=False) == 500
    assert Plan._mipNodeLimit({"mipMaxNodes": 500.0}, mosek=True) == 500


def test_pure_lp_reports_no_nodes():
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105})
    assert p.caseStatus == "solved"
    assert p.solverNodes == -1 and p.solverNodesTotal == -1
    dic = p.summaryDic()
    assert dic[NODES_ROW].startswith("n/a")
    assert LIMIT_ROW in dic


def test_mip_reports_nodes():
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105, "withdrawalOrder": "taxable_first"})
    assert p.caseStatus == "solved"
    assert 0 <= p.solverNodes <= p.solverNodesTotal
    accepted, total = p.summaryDic()[NODES_ROW].split(" / ")
    assert int(accepted.replace(",", "")) == p.solverNodes
    assert int(total.replace(",", "")) == p.solverNodesTotal


def test_mip_max_nodes_is_a_solver_option():
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105, "withdrawalOrder": "taxable_first", "mipMaxNodes": 250_000})
    assert p.solverOptions["mipMaxNodes"] == 250_000
    unit = "branches (MOSEK)" if p._use_mosek else "nodes (HiGHS)"
    assert p.summaryDic()[LIMIT_ROW] == f"250,000 {unit}"


def test_a_new_solve_resets_the_tally():
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105, "withdrawalOrder": "taxable_first"})
    assert p.solverNodesTotal >= 0
    p.solve("maxBequest", {"netSpending": 105})
    assert p.solverNodes == -1 and p.solverNodesTotal == -1


STEP_ROW = "Local search step node limit"


def test_step_limit_reads_na_without_local_search():
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105, "withdrawalOrder": "taxable_first"})
    assert p.summaryDic()[STEP_ROW] == "n/a (no local search)"


def test_step_limit_reports_default_and_option():
    # The row reads only the solver options and the engine: no need for a (slow) local-search solve.
    p = _plan()
    for mosek, engine, unit in ((False, "HiGHS", "nodes"), (True, "MOSEK", "branches")):
        p._use_mosek = mosek
        p.solverOptions = {"mipStrategy": "local-search"}
        assert _local_search_step_limit(p) == f"{localsearch.STEP_NODES[engine]:,} {unit} ({engine})"
        p.solverOptions["localSearchStepNodes"] = 4321
        assert _local_search_step_limit(p) == f"4,321 {unit} ({engine})"


HITS_ROW = "MIP solves stopped at node limit"
MIP_OPTS = {"netSpending": 105, "withdrawalOrder": "taxable_first"}


def test_node_limit_hits_read_na_for_a_pure_lp():
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105})
    assert p.solverNodeLimitHits is None
    assert p.summaryDic()[HITS_ROW] == "n/a (no mixed-integer solve)"


def test_uncapped_solves_do_not_reach_the_limit():
    p = _plan()
    p.solve("maxBequest", dict(MIP_OPTS))
    capped, runs, steps_capped, steps = p.solverNodeLimitHits
    assert capped == 0 and runs > 0 and steps == steps_capped == 0
    assert p.summaryDic()[HITS_ROW] == f"0 of {runs}"


def test_capped_solves_are_counted_and_reset():
    p = _plan()
    p.solve("maxBequest", dict(MIP_OPTS, mipMaxNodes=1))
    capped, runs, _, _ = p.solverNodeLimitHits
    assert runs > 0 and capped == runs
    p.solve("maxBequest", {"netSpending": 105})
    assert p.solverNodeLimitHits is None


def test_local_search_steps_are_counted_apart():
    # A one-node step cap stops the steps, not the loop that seeds the search; the counts survive
    # the search falling back to the loop's plan.
    p = _plan()
    p.solve("maxBequest", {"netSpending": 105, "mipStrategy": "local-search", "withMedicare": "optimize",
                           "localSearchStepNodes": 1})
    capped, runs, steps_capped, steps = p.solverNodeLimitHits
    assert capped == 0 and steps > 0 and 0 < steps_capped <= steps
    assert p.summaryDic()[HITS_ROW] == f"0 of {runs} (local search steps: {steps_capped} of {steps})"
