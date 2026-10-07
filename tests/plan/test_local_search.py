"""
Local search (mipStrategy="local-search"): fix-and-optimize over the threshold binaries.

The guarantees under test: the result is never worse than the self-consistent loop's plan, the
full MILP is never solved, a search that cannot start keeps the loop's plan and says so, and the
Summary always reports how the thresholds were treated.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import pathlib
import time

import pytest

import owlplanner as owl
from owlplanner import localsearch
from owlplanner.config import config_to_ui, ui_to_config, load_toml

_EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"


def _load(case="Case_jack+jill.toml"):
    return owl.readConfig(str(_EXAMPLES / case), verbose=False, logstreams=[io.StringIO()])


def _value(p):
    return p.g_n[0] if p.objective == "maxSpending" else p.bequest


def _loop_options(p):
    """The case's own options with every threshold family in loop mode (the search's floor)."""
    opts = dict(p.solverOptions)
    for k in ("withSSTaxability", "withLTCG", "withNIIT", "withACA", "withMedicare"):
        if opts.get(k) == "optimize":
            opts[k] = "loop"
    return opts


@pytest.fixture(scope="module")
def jack_jill_pair():
    """The same case solved by the loop and by local search."""
    loop = _load()
    loop.solve(loop.objective, options=_loop_options(loop))
    ls = _load()
    ls.solve(ls.objective, options={**ls.solverOptions, "breakpointMethod": "local-search"})
    return loop, ls


@pytest.mark.toml
def test_never_worse_than_the_loop(jack_jill_pair):
    loop, ls = jack_jill_pair
    assert loop.caseStatus == "solved" and ls.caseStatus == "solved"
    assert _value(ls) >= _value(loop) - 1.0
    assert ls.breakpointMethodUsed.startswith("local search")
    assert ls.localSearchLog, "the search kept no log"


@pytest.mark.toml
def test_never_solves_the_full_milp(jack_jill_pair):
    """Every step is a restricted problem: something is pinned, or it is an LP or a repair."""
    _, ls = jack_jill_pair
    for it in ls.localSearchLog:
        for step in it["steps"]:
            assert step["step"].startswith(("start:", "round")), step["step"]


@pytest.mark.toml
def test_no_starting_plan_keeps_the_loop(monkeypatch):
    def no_start(self, options, steps):
        raise localsearch.NoIncumbent()

    monkeypatch.setattr(localsearch.LocalSearch, "_incumbent", no_start)
    loop = _load()
    loop.solve(loop.objective, options=_loop_options(loop))
    p = _load()
    p.solve(p.objective, options={**p.solverOptions, "breakpointMethod": "local-search"})
    assert p.caseStatus == "solved"
    assert _value(p) == pytest.approx(_value(loop), rel=1e-9)
    assert p.breakpointMethodUsed == "local search -> loop"
    # The case keeps the strategy it asked for, for saving and for the UI.
    assert p.solverOptions["breakpointMethod"] == "local-search"


@pytest.mark.toml
def test_time_budget_is_respected():
    """With no budget the search stops after its starting plan, still never below the loop."""
    loop = _load()
    loop.solve(loop.objective, options=_loop_options(loop))
    p = _load()
    t = time.time()
    p.solve(p.objective, options={**p.solverOptions, "breakpointMethod": "local-search", "localSearchTime": 0})
    assert time.time() - t < 120
    assert p.caseStatus == "solved"
    assert _value(p) >= _value(loop) - 1.0
    for it in p.localSearchLog:
        assert all(s["step"].startswith("start:") for s in it["steps"])


def test_preset_sets_the_families_and_the_strategy():
    p = _load()
    opts = {"breakpointMethod": "local-search", "withMedicare": "loop"}
    p._applyBreakpointOptions(opts)
    for k in ("withSSTaxability", "withLTCG", "withNIIT", "withMedicare"):
        assert opts[k] == "optimize", k
    assert opts["mipStrategy"] == "local-search"
    assert "withACA" not in opts  # no benchmark premium in this case

    off = {"breakpointMethod": "branch-and-bound", "withMedicare": "None"}
    p._applyBreakpointOptions(off)
    assert off["withMedicare"] == "None" and off["mipStrategy"] == "branch-and-bound"

    unchanged = {"breakpointMethod": "loop"}
    p._applyBreakpointOptions(unchanged)
    assert unchanged == {"breakpointMethod": "loop"}


@pytest.mark.parametrize("opts", [{"breakpointMethod": "exact"}, {"mipStrategy": "exact"}])
def test_invalid_values_are_rejected(opts):
    with pytest.raises(ValueError):
        _load()._applyBreakpointOptions(dict(opts))


def test_claiming_ages_and_ordering_go_to_branch_and_bound():
    p = _load()
    for extra in ({"withSSAges": "optimize"}, {"withdrawalOrder": "taxable_first"}):
        opts = {"withNIIT": "optimize", "mipStrategy": "local-search", **extra}
        assert not p._useLocalSearch(opts)
        assert opts["mipStrategy"] == "branch-and-bound"


def test_threshold_method_label():
    p = _load()
    assert p._breakpointMethodLabel({}) == "loop"
    assert p._breakpointMethodLabel({"withNIIT": "optimize"}) == "branch-and-bound (NIIT)"
    both = {"withSSTaxability": "optimize", "withLTCG": "optimize", "mipStrategy": "local-search"}
    assert p._breakpointMethodLabel(both) == "local search (SS, LTCG)"
    assert p._breakpointMethodLabel(both, fallback=True) == "local search -> loop"
    # ACA only counts when a benchmark premium is set.
    assert p._breakpointMethodLabel({"withACA": "optimize"}) == "loop"


@pytest.mark.toml
def test_summary_always_reports_the_threshold_method(jack_jill_pair):
    loop, ls = jack_jill_pair
    assert loop.summaryDic()["Breakpoint method"] == "loop"
    assert ls.summaryDic()["Breakpoint method"].startswith("local search (")


@pytest.mark.toml
def test_ui_round_trip():
    diconf, _, _ = load_toml(str(_EXAMPLES / "Case_jack+jill.toml"))
    diconf["solver_options"]["breakpointMethod"] = "local-search"
    ui = config_to_ui(diconf)
    assert ui["localSearch"] is True
    assert ui_to_config(ui)["solver_options"]["breakpointMethod"] == "local-search"

    diconf["solver_options"].pop("breakpointMethod")
    diconf["solver_options"]["mipStrategy"] = "local-search"
    ui = config_to_ui(diconf)
    assert ui["localSearch"] is False and ui["mipStrategy"] == "local-search"
    assert ui_to_config(ui)["solver_options"]["mipStrategy"] == "local-search"

    diconf["solver_options"].pop("mipStrategy")
    out = ui_to_config(config_to_ui(diconf))["solver_options"]
    assert "mipStrategy" not in out and "breakpointMethod" not in out


def test_restricted_solves_use_a_tight_gap(monkeypatch):
    """A loose solve gap (0.3%, as applied when Medicare is MILP) must not reach the restricted
    solves: it stopped them before the 0.1% partial-bequest weight counted, and money the household
    did not need was spent to no purpose."""
    from datetime import date

    from owlplanner import plan as P

    gaps = []
    orig = P.Plan._run_mip

    def spy(self, A, B, c_obj, options, *args, **kwargs):
        gaps.append(float(options.get("gap", -1)))
        return orig(self, A, B, c_obj, options, *args, **kwargs)

    monkeypatch.setattr(P.Plan, "_run_mip", spy)
    thisyear = date.today().year
    p = owl.Plan(["Jack", "Jill"], [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"], [72, 72], "gap",
                 verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[1500, 1000], taxDeferred=[3000, 2000], taxFree=[50, 50], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]], [[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSocialSecurity([2000, 1500], [67, 67])
    p.setRates("historical", 2000)
    p.solve("maxSpending", {"breakpointMethod": "local-search", "gap": 0.003, "maxIter": 3})
    assert p.caseStatus == "solved"
    assert gaps, "local search made no restricted solve"
    assert max(gaps) <= 1e-4, max(gaps)


def _residual(p):
    return sum(v["abs_sum"] for v in p.fixedPointResidual.values())


@pytest.mark.toml
def test_tie_keeps_the_consistent_plan():
    """cameron's loop ends on a 2-cycle whose plan charges ~$30k of taxable Social Security its
    income does not imply. The search ties its objective with a consistent plan; the tie must not
    hand back the inconsistent one."""
    loop = _load("Case_cameron.toml")
    loop.solve(loop.objective, options=_loop_options(loop))
    ls = _load("Case_cameron.toml")
    ls.solve(ls.objective, options={**ls.solverOptions, "breakpointMethod": "local-search"})
    assert _residual(loop) > 1000.0, _residual(loop)
    assert _value(ls) >= _value(loop) - 1.0
    assert _residual(ls) < 10.0, _residual(ls)
    assert "->" not in ls.breakpointMethodUsed, ls.breakpointMethodUsed


@pytest.mark.toml
def test_repeated_problem_is_not_searched_again():
    """The loop stops when two iterations agree, so its last one rebuilds the problem it just
    solved: the search returns that iteration's plan without running a single restricted solve."""
    p = _load("Case_cameron.toml")
    p.solve(p.objective, options={**p.solverOptions, "breakpointMethod": "local-search"})
    log = p.localSearchLog
    assert len(log) >= 2 and log[0]["steps"], log
    assert log[-1]["steps"] == [], log[-1]
