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


@pytest.mark.toml
def test_dana_1966_maxspending_reference(dana):
    """Pin the paper's 1966 maxSpending numbers (Cost-of-Committing sweep, 2026-07-16)."""
    opts = dict(dana.solverOptions)
    opts["solver"] = "HiGHS"  # reference values are HiGHS numbers
    res = run_conversion_regret_sweep(
        dana, "maxSpending", opts, [0, 60_000, 120_000], 1966, 1966, include_never_convert=False
    )
    assert res["start_years"].tolist() == [1966]
    assert _rel(res["v_star"][0], 58_230.17) < RTOL
    assert _rel(res["x_star"][0], 65_491.05) < RTOL
    assert _rel(res["v_at"][0, 0], 58_201.80) < RTOL
    assert _rel(res["v_at"][0, 1], 58_242.17) < RTOL
    assert _rel(res["v_at"][0, 2], 58_083.44) < RTOL
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
    assert _rel(res["v_star"][0], 421_691.64) < RTOL
    assert _rel(res["x_star"][0], 65_496.69) < RTOL
    assert _rel(res["v_at"][0, 0], 413_929.27) < RTOL
    assert _rel(res["v_at"][0, 1], 415_014.46) < RTOL
    assert _rel(res["v_noconv"][0], 395_926.80) < RTOL
    # Orderings that carry the paper's story, all far above the noise floor:
    # never converting < skipping year 1 < converting near the optimum <= clairvoyant.
    assert res["v_noconv"][0] < res["v_at"][0, 0] < res["v_at"][0, 1] <= res["v_star"][0] + NOISE

    s = summarize_conversion_regret(res)
    assert s["n_scenarios"] == 1
    # summarize_conversion_regret rounds to cents.
    assert s["never_convert_regret"]["mean"] == pytest.approx(
        res["v_star"][0] - res["v_noconv"][0], abs=0.01
    )
