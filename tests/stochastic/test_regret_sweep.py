"""
Tests for the commitment regret sweep: run_conversion_regret_sweep and summarize_conversion_regret.

Coverage:
  - summarize_conversion_regret: pure aggregation on a hand-built result (stats, valley,
    asymmetry interpolation, infeasible counting, never-convert stats)
  - run_conversion_regret_sweep on the dana example case, pinned against reference values
    from the original Cost-of-Committing sweeps (2026-07-16, HiGHS): the tool
    must keep reproducing the published numbers
  - structural invariants: pinning at the scenario optimum is near-lossless,
    never converting is worse than converting, argument validation

The reference tests pin solver="HiGHS" regardless of OWL_TEST_SOLVER: the
published values are HiGHS numbers, and on the bequest objective the SC loop can
land on a different fixed point per solver (MOSEK's pinned-at-zero 1966 solve is
~$6k above HiGHS's), which is solver sensitivity to document, not test noise.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import numpy as np
import pytest

from owlplanner import run_conversion_regret_sweep, summarize_conversion_regret
from owlplanner.stresstests import (
    REGRET_MAX_GAP,
    _regret_objective_value,
    _build_regret_grid,
    _downgrade_milp_tax_modes,
    _select_regret_years,
)
from owlplanner.config import readConfig

DANA_TOML = "examples/Case_dana.toml"
RTOL = 5e-3
NOISE = 200.0  # SC-loop fixed-point noise floor on spending levels, $/yr


@pytest.fixture(scope="module")
def dana():
    return readConfig(DANA_TOML, verbose=False)


def _rel(a, b):
    return abs(a - b) / max(abs(b), 1.0)


def test_summarize_conversion_regret_pure():
    grid = [0.0, 50_000.0, 100_000.0]
    result = {
        "grid": grid,
        "start_years": np.array([1990, 1991, 1992]),
        # scenario 2's baseline failed; scenario 1 infeasible at x=100k
        "v_star": np.array([100_000.0, 80_000.0, np.nan]),
        "x_star": np.array([50_000.0, 0.0, np.nan]),
        "v_at": np.array(
            [
                [99_000.0, 100_000.0, 98_000.0],
                [80_000.0, 79_000.0, np.nan],
                [np.nan, np.nan, np.nan],
            ]
        ),
        "v_noconv": np.array([98_500.0, 80_000.0, np.nan]),
        "person": 0,
    }
    s = summarize_conversion_regret(result, asymmetry_deltas=(50_000,))

    assert s["n_scenarios"] == 2
    assert s["n_failed_baselines"] == 1
    # Regret at x=0: [1000, 0]; at 50k: [0, 1000]; at 100k: [2000, infeasible]
    assert s["regret_by_grid"][0]["mean"] == 500.0
    assert s["regret_by_grid"][1]["mean"] == 500.0
    assert s["regret_by_grid"][2] == {"x": 100_000.0, "mean": 2000.0, "median": 2000.0,
                                      "p90": 2000.0, "max": 2000.0, "n_infeasible": 1}
    assert s["valley"]["x"] in (0.0, 50_000.0)
    assert s["x_star"]["share_converting"] == 0.5
    # Asymmetry at delta=50k: over = R(x*+50k) = [2000 (s0), 1000 (s1)];
    # under floors at x=0 = [1000 (s0), 0 (s1)]
    a = s["asymmetry"][0]
    assert a["n_over"] == 2 and a["n_under"] == 2
    assert a["mean_regret_over"] == 1500.0
    assert a["mean_regret_under"] == 500.0
    assert a["over_under_ratio"] == 3.0
    # Never-convert regret: [1500, 0]
    assert s["never_convert_regret"]["mean"] == 750.0
    assert s["never_convert_regret"]["max"] == 1500.0


def test_rejects_bad_arguments(dana):
    opts = dict(dana.solverOptions)
    with pytest.raises(ValueError, match="grid"):
        run_conversion_regret_sweep(dana, "maxSpending", opts, [], 1966, 1966)
    with pytest.raises(ValueError, match="grid"):
        run_conversion_regret_sweep(dana, "maxSpending", opts, [-5.0], 1966, 1966)
    with pytest.raises(ValueError, match="person"):
        run_conversion_regret_sweep(dana, "maxSpending", opts, [0.0], 1966, 1966, person=3)


# Values refreshed 2026-08-11 when the AMO exclusion binaries were removed. The maxSpending
# numbers moved by less than 0.11%. The maxBequest baseline moved more, v_star 421_691.64 ->
# 415_402.15, and the reason is worth recording: the old solve terminated on "max iteration"
# without ever converging, so its value was the best of 29 iterations, while the same solve
# now detects the cycle and terminates as "oscillatory". The manuscript's never-convert regret
# is computed as v_star - v_noconv, and v_noconv is unchanged, so that headline figure moves
# from 25_764.84 to 19_475.35. The paper's ordering still holds, but the magnitude does not.
@pytest.mark.toml
def test_dana_1966_maxspending_reference(dana):
    """Pin the paper's 1966 maxSpending numbers (Cost-of-Committing sweep, 2026-07-16)."""
    opts = dict(dana.solverOptions)
    opts["solver"] = "HiGHS"  # reference values are HiGHS numbers
    res = run_conversion_regret_sweep(
        dana, "maxSpending", opts, [0, 60_000, 120_000], 1966, 1966, include_never_convert=False
    )
    assert res["start_years"].tolist() == [1966]
    assert _rel(res["v_star"][0], 58_208.39) < RTOL
    assert _rel(res["x_star"][0], 65_491.59) < RTOL
    assert _rel(res["v_at"][0, 0], 58_194.28) < RTOL
    assert _rel(res["v_at"][0, 1], 58_207.44) < RTOL
    assert _rel(res["v_at"][0, 2], 58_018.64) < RTOL
    # Pinned solves can beat the SC-loop baseline only within the noise floor.
    regret = res["v_star"][0] - res["v_at"][0, :]
    assert (regret > -NOISE).all()


@pytest.mark.toml
def test_dana_1966_maxbequest_reference(dana):
    """Pin the paper's 1966 maxBequest numbers, including the never-convert benchmark."""
    opts = dict(dana.solverOptions)
    opts["solver"] = "HiGHS"  # reference values are HiGHS numbers
    opts.pop("bequest", None)
    opts["netSpending"] = 58.0  # $k; the scenario-minimum spending used in the paper
    res = run_conversion_regret_sweep(dana, "maxBequest", opts, [0, 63_636], 1966, 1966)
    assert _rel(res["v_star"][0], 415_402.15) < RTOL
    assert _rel(res["x_star"][0], 65_496.69) < RTOL
    assert _rel(res["v_at"][0, 0], 414_463.13) < RTOL
    assert _rel(res["v_at"][0, 1], 415_478.78) < RTOL
    assert _rel(res["v_noconv"][0], 395_926.80) < RTOL
    # Orderings that carry the paper's story:
    # never converting < skipping year 1 < converting near the optimum <= clairvoyant.
    # The last link now leans on NOISE: a pinned solve comes back $77 above the SC-loop
    # baseline, which is a reminder that v_star is a baseline solve and not a proven bound.
    assert res["v_noconv"][0] < res["v_at"][0, 0] < res["v_at"][0, 1] <= res["v_star"][0] + NOISE

    s = summarize_conversion_regret(res)
    assert s["n_scenarios"] == 1
    # summarize_conversion_regret rounds to cents.
    assert s["never_convert_regret"]["mean"] == pytest.approx(
        res["v_star"][0] - res["v_noconv"][0], abs=0.01
    )


class TestOutcomeUnits:
    """
    maxSpending regret is quoted in the first year's net spending, not the profile-neutral
    basis the optimizer maximizes. The two coincide on a flat profile and differ by the
    profile factor otherwise, and the first year's amount is what netSpending pins.
    """

    @pytest.mark.toml
    def test_flat_profile_makes_basis_and_year_one_identical(self):
        p = readConfig("examples/Case_dana.toml", verbose=False)
        assert p.spendingProfile == "flat"
        p.setRates("historical", 1966)
        p.solve("maxSpending", options={"solver": "HiGHS"})
        assert _regret_objective_value(p, "maxSpending") == pytest.approx(p.basis)

    @pytest.mark.toml
    def test_a_smile_profile_reports_year_one_not_the_basis(self):
        p = readConfig("examples/Case_jack+jill.toml", verbose=False)
        assert p.spendingProfile == "smile"
        p.setRates("historical", 1966)
        p.solve("maxSpending", options={"solver": "HiGHS"})
        xi0 = float(p.xi_n[0])
        assert xi0 > 1.05, "expected a profile factor worth distinguishing"
        got = _regret_objective_value(p, "maxSpending")
        assert got == pytest.approx(p.basis * xi0)
        assert got != pytest.approx(p.basis), "reporting the basis would understate spending"


class TestGridAndScenarioSelection:
    """The two-phase sweep sizes its own grid and picks its own windows."""

    def test_grid_spans_the_widest_optimum_plus_padding(self):
        x_star = np.array([10_000.0, 90_000.0, np.nan, 40_000.0])
        grid = _build_regret_grid(x_star, n_grid=7, pad=45_000.0)
        assert len(grid) == 7
        assert grid[0] == 0.0
        # The padding keeps the over-conversion probes on-grid; without it they would be
        # dropped and the over/under means would be taken over different subsets.
        assert grid[-1] == pytest.approx(135_000.0)
        assert all(b > a for a, b in zip(grid, grid[1:]))

    def test_grid_survives_a_case_that_never_converts(self):
        """All-zero optima must still give a usable grid rather than a degenerate one."""
        grid = _build_regret_grid(np.zeros(5), n_grid=5, pad=45_000.0)
        assert grid[0] == 0.0 and grid[-1] == pytest.approx(45_000.0)

    def test_subsampling_is_random_not_stride(self):
        years = range(1928, 2000)
        picked, seed = _select_regret_years(years, 24, 7)
        assert len(picked) == 24 and len(set(picked)) == 24
        assert picked == sorted(picked) and seed == 7
        # A stride would leave a constant gap. Adjacent windows overlap heavily, so a
        # stride lands on a correlated run and biases the valley (measured at -$16k).
        gaps = {b - a for a, b in zip(picked, picked[1:])}
        assert len(gaps) > 1

    def test_subsampling_is_reproducible_from_the_seed(self):
        a, _ = _select_regret_years(range(1928, 2000), 20, 42)
        b, _ = _select_regret_years(range(1928, 2000), 20, 42)
        c, _ = _select_regret_years(range(1928, 2000), 20, 43)
        assert a == b and a != c

    def test_asking_for_every_window_sweeps_them_all(self):
        picked, seed = _select_regret_years(range(1990, 2000), None, 1)
        assert picked == list(range(1990, 2000)) and seed is None
        picked, _ = _select_regret_years(range(1990, 2000), 500, 1)
        assert picked == list(range(1990, 2000))


class TestNeverConvertIsNested:
    """
    Regret cannot be negative: the never-convert solve must be a strict restriction of the
    clairvoyant baseline.

    The trap is a case that already excludes the *other* spouse via
    options["noRothConversions"], which names one individual. Overwriting that option with
    the pinned person's name would free the excluded spouse, leaving the two solves
    un-nested and producing a large negative "value of converting".
    """

    @pytest.mark.toml
    def test_regret_stays_non_negative_when_the_case_excludes_the_spouse(self):
        plan = readConfig("examples/Case_jack+jill.toml", verbose=False)
        opts = dict(plan.solverOptions)
        opts.update({"solver": "HiGHS", "noRothConversions": plan.inames[1]})
        res = run_conversion_regret_sweep(plan, "maxSpending", opts, [0.0], 1970, 1972, person=0)
        ok = ~np.isnan(res["v_star"])
        assert ok.any()
        # Tolerance is relative to the objective. Under maxSpending the outcome is the
        # first-year basis, on which the self-consistent tax loop leaves noise of order
        # 1e-4 to 1e-3; the defect this guards against was 60% of the objective, so a 1e-3
        # bound separates the two by nearly three orders of magnitude.
        floor = -1e-3 * np.abs(res["v_star"][ok])
        never = res["v_star"][ok] - res["v_noconv"][ok]
        assert np.all(never >= floor), f"never-convert regret went materially negative: {never}"
        pinned = res["v_star"][ok, None] - res["v_at"][ok, :]
        assert np.all(np.nan_to_num(pinned, nan=0.0) >= floor[:, None])

    @pytest.mark.toml
    def test_the_case_own_exclusion_is_not_discarded(self):
        """The spouse the case excludes must stay excluded in every solve of the sweep."""
        plan = readConfig("examples/Case_jack+jill.toml", verbose=False)
        opts = dict(plan.solverOptions)
        opts.update({"solver": "HiGHS", "noRothConversions": plan.inames[1]})
        run_conversion_regret_sweep(plan, "maxSpending", opts, [0.0], 1970, 1970, person=0)
        assert opts["noRothConversions"] == plan.inames[1]


class TestGapGuard:
    """Solver tolerance must never be looser than the regret being measured."""

    def test_an_absent_gap_is_pinned_tight(self, dana):
        """
        Owl otherwise adopts a loose MIP gap (30x GAP, 10x more for a small cap) when a tax
        mode is optimized, which would exceed the ~1e-3 relative regret near the valley.
        """
        opts = {"solver": "HiGHS", "netSpending": 58.0, "withMedicare": "optimize"}
        run_conversion_regret_sweep(dana, "maxBequest", opts, [0.0], 1966, 1966, milp_downgrade=True)
        assert "gap" not in opts, "must not mutate the caller's options"

    def _sweep_with_gap(self, dana, gap):
        opts = dict(dana.solverOptions)
        opts.update({"solver": "HiGHS"})
        opts.pop("bequest", None)
        opts["netSpending"] = 58.0
        if gap is not None:
            opts["gap"] = gap
        return run_conversion_regret_sweep(dana, "maxBequest", opts, [0.0], 1966, 1966)["solver_gap"]

    def test_a_loose_gap_is_tightened(self, dana):
        assert self._sweep_with_gap(dana, 1e-2) == REGRET_MAX_GAP

    def test_a_gap_already_tight_is_left_alone(self, dana):
        """Reproducing a published run at 1e-8 must not be quietly coarsened to the cap."""
        assert self._sweep_with_gap(dana, 1e-9) == 1e-9

    def test_no_gap_at_all_is_pinned_to_the_cap(self, dana):
        assert self._sweep_with_gap(dana, None) == REGRET_MAX_GAP


class TestMilpDowngrade:
    def test_only_optimize_modes_are_flipped(self):
        opts = {"withMedicare": "optimize", "withACA": "loop", "withNIIT": "optimize", "gap": 1e-6}
        out, changed = _downgrade_milp_tax_modes(opts)
        assert changed == ["withMedicare", "withNIIT"]
        assert out["withMedicare"] == "loop" and out["withNIIT"] == "loop"
        assert out["withACA"] == "loop" and out["gap"] == 1e-6
        assert opts["withMedicare"] == "optimize", "must not mutate the caller's options"

    def test_ss_ages_are_left_alone(self):
        """withSSAges picks a claiming age; it has no loop equivalent to fall back on."""
        out, changed = _downgrade_milp_tax_modes({"withSSAges": "optimize"})
        assert changed == [] and out["withSSAges"] == "optimize"


class TestSummaryRobustnessLayer:
    """The readouts that decide what the plot is allowed to claim."""

    @staticmethod
    def _valley_result(depth=20_000.0, n=24):
        """A clean V-shaped curve: every scenario prefers the middle of the grid."""
        grid = [0.0, 25_000.0, 50_000.0, 75_000.0, 100_000.0]
        v_star = np.full(n, 500_000.0)
        shape = np.array([depth, depth / 4, 0.0, depth / 4, depth])
        v_at = v_star[:, None] - shape[None, :]
        return {"grid": grid, "start_years": np.arange(1950, 1950 + n),
                "v_star": v_star, "x_star": np.full(n, 50_000.0), "v_at": v_at,
                "v_noconv": v_star - 200_000.0, "person": 0}

    def test_a_clear_valley_is_reported_with_an_interval(self):
        s = summarize_conversion_regret(self._valley_result())
        assert s["valley"]["x"] == 50_000.0
        assert s["valley_resolvable"] is True
        assert s["valley_ci"]["p10"] <= 50_000.0 <= s["valley_ci"]["p90"]
        assert len(s["mean_ci_by_grid"]) == 5

    def test_a_flat_curve_refuses_to_name_a_valley(self):
        """Below the resolution floor there is nothing to report, and saying so is the answer."""
        s = summarize_conversion_regret(self._valley_result(depth=0.0))
        assert s["valley_resolvable"] is False

    def test_commit_band_widens_with_the_tolerance(self):
        r = self._valley_result()
        narrow = summarize_conversion_regret(r, band_frac=0.001)["commit_band"]
        wide = summarize_conversion_regret(r, band_frac=0.05)["commit_band"]
        assert narrow["x_lo"] >= wide["x_lo"] and narrow["x_hi"] <= wide["x_hi"]
        assert wide["x_lo"] <= 50_000.0 <= wide["x_hi"]

    def test_bootstrap_is_deterministic(self):
        r = self._valley_result()
        assert (summarize_conversion_regret(r)["valley_ci"]
                == summarize_conversion_regret(r)["valley_ci"])

    def test_a_case_that_cannot_convert_is_reported_as_such(self):
        """
        maxRothConversion of zero, or no tax-deferred balance, makes every commitment above
        zero infeasible. That is a different statement from "the curve is flat", and must not
        be dressed up as one.
        """
        r = self._valley_result()
        r["v_at"][:, 1:] = np.nan          # nothing above the first grid point solves
        s = summarize_conversion_regret(r)
        assert s["conversions_blocked"] is True

    def test_one_surviving_scenario_is_not_a_curve(self):
        """A mean over a single feasible scenario is worse than none: still 'blocked'."""
        r = self._valley_result()
        r["v_at"][1:, 1:] = np.nan         # exactly one scenario survives above zero
        s = summarize_conversion_regret(r)
        assert s["conversions_blocked"] is True

    def test_a_normal_case_is_not_flagged_as_blocked(self):
        assert summarize_conversion_regret(self._valley_result())["conversions_blocked"] is False

    def test_a_minimum_on_the_last_grid_point_is_flagged_as_unbracketed(self):
        """
        A valley at the right edge means the curve was still falling when the grid ran
        out, so the answer is a lower bound, not a located optimum.
        """
        r = self._valley_result()
        # Monotonically decreasing across the whole grid: the minimum is the last point.
        r["v_at"] = r["v_star"][:, None] - np.array([40_000.0, 30_000.0, 20_000.0, 10_000.0, 0.0])[None, :]
        s = summarize_conversion_regret(r)
        assert s["valley"]["x"] == 100_000.0
        assert s["valley_at_grid_edge"] is True

    def test_an_interior_minimum_is_not_flagged(self):
        s = summarize_conversion_regret(self._valley_result())
        assert s["valley_at_grid_edge"] is False

    def test_a_minimum_at_zero_is_not_flagged(self):
        """Zero is a real boundary -- a conversion cannot be negative -- not a grid artifact."""
        r = self._valley_result()
        r["v_at"] = r["v_star"][:, None] - np.array([0.0, 10_000.0, 20_000.0, 30_000.0, 40_000.0])[None, :]
        s = summarize_conversion_regret(r)
        assert s["valley"]["x"] == 0.0
        assert s["valley_at_grid_edge"] is False

    def test_negative_regret_raises_the_resolution_floor(self):
        """
        Regret cannot be negative: pinning is a restriction. A negative value is therefore a
        direct measurement of the method's own error, and the floor must reflect it. It is
        deterministic and survives an arbitrarily tight solver gap, so it cannot be inferred
        from the solver.
        """
        clean = summarize_conversion_regret(self._valley_result())
        r = self._valley_result()
        r["v_at"][0, 2] = r["v_star"][0] + 6_000.0        # one scenario reads -6,000
        dirty = summarize_conversion_regret(r)
        assert dirty["resolution_floor"] > clean["resolution_floor"]
        # Cell error averages down across scenarios: |worst| / sqrt(n), not |worst|.
        assert dirty["resolution_floor"] == pytest.approx(6_000.0 / np.sqrt(24), rel=0.15)

    def test_a_flat_bottom_is_not_a_located_valley(self):
        """
        A curve can rise steeply at one end while its bottom is a plateau. Naming one grid
        point as the best commitment is then false precision, however wide the curve's range.
        """
        grid = [0.0, 25_000.0, 50_000.0, 75_000.0, 100_000.0]
        n = 24
        v_star = np.full(n, 500_000.0)
        # Steep on the left, indistinguishable across the whole right-hand half.
        shape = np.array([40_000.0, 12_000.0, 5.0, 0.0, 3.0])
        r = {"grid": grid, "start_years": np.arange(1950, 1950 + n), "v_star": v_star,
             "x_star": np.full(n, 60_000.0), "v_at": v_star[:, None] - shape[None, :],
             "v_noconv": v_star - 200_000.0, "person": 0}
        # Give it a floor big enough to swallow the plateau but not the curve's range.
        r["v_at"][0, 3] = v_star[0] + 3_000.0
        s = summarize_conversion_regret(r)
        assert s["n_within_floor"] >= 3
        assert s["valley_resolvable"] is False, "a plateau must not be reported as a valley"

    def test_a_clear_valley_survives_the_plateau_test(self):
        s = summarize_conversion_regret(self._valley_result())
        assert s["valley_resolvable"] is True
        assert s["n_within_floor"] <= 2

    def test_percentage_axis_is_refused_when_converting_is_worthless(self):
        """
        Never-convert regret is large under maxBequest but can be ~0 or negative under
        maxSpending, where normalizing by it would be meaningless or sign-flipped.
        """
        r = self._valley_result()
        r["v_noconv"] = r["v_star"] + 5.0  # converting is worth nothing at all here
        s = summarize_conversion_regret(r)
        assert s["pct_axis_ok"] is False
        assert "commit_band" not in s
        assert s["value_of_converting"] is not None


@pytest.mark.toml
def test_auto_grid_end_to_end(dana):
    """
    Passing grid=None must size the grid from the scenarios themselves, which is what
    removes the separate probe sweep the published runs needed.
    """
    opts = dict(dana.solverOptions)
    opts["solver"] = "HiGHS"
    opts.pop("bequest", None)
    opts["netSpending"] = 58.0
    res = run_conversion_regret_sweep(dana, "maxBequest", opts, None, 1966, 1967, n_grid=5, grid_pad=45_000.0)

    assert len(res["grid"]) == 5
    assert res["grid"][0] == 0.0
    assert res["grid"][-1] == pytest.approx(float(np.nanmax(res["x_star"])) + 45_000.0, abs=1.0)
    assert res["v_at"].shape == (2, 5)
    assert res["milp_downgraded"] == []

    s = summarize_conversion_regret(res)
    # Regret is non-negative by construction; only solver noise can push it below zero,
    # and never by more than the resolution floor.
    for g in s["regret_by_grid"]:
        if g["mean"] is not None:
            assert g["mean"] >= -s["resolution_floor"] - 1.0
