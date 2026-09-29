"""
A pinned rate seed must reproduce the same series on every machine.

Correlated draws once went through the default SVD factorization of the covariance.
An SVD is only determined up to conventions that differ between LAPACK builds, so the
same seed produced unrelated series on macOS and Linux, and `Case_chris+pat` -- the one
shipped example that draws its returns -- solved 17% apart between them.

The values below were recorded on macOS. They are asserted rather than merely compared
against a second local run because the property at issue is cross-platform: a local run
cannot detect the failure at all, and CI on Linux is what actually tests it. A mismatch
here means a seeded series is once again machine-dependent, which quietly invalidates
any Monte Carlo result anyone tries to reproduce elsewhere.

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

import os

import numpy as np
import pytest

import owlplanner as owl
from owlplanner.rate_models import _sampling

# Only the factorization was pinned, not the arithmetic around it, so a different BLAS
# may still differ in the last bits. That is nothing like the failure being guarded
# against, where entire draws changed, so the tolerance is tight but not exact.
RTOL = 1e-9

# Reproducibility was already tested, but only against itself: test_repro.py builds two
# plans on one machine and compares them, which cannot see a factorization that differs
# between machines. These references are what makes the guarantee portable -- CI on Linux
# is the only thing that actually exercises it.

# examples/Case_chris+pat.toml, method historical_lognormal, rate_seed 2026.
# First three years, four asset classes. Recorded on darwin, 2026-08-12.
CHRIS_PAT_FIRST_YEARS = np.array(
    [
        [-0.052778640806826, 0.055571513781582, -0.041408929662749, 0.081734169199666],
        [0.241031172520921, 0.068217765741840, 0.013832513973259, 0.045402036114079],
        [0.045978746612122, 0.041870930372280, 0.071587808447754, 0.051001821293578],
    ]
)


@pytest.mark.toml
def test_seeded_case_series_matches_reference():
    """The shipped stochastic example must draw the same returns everywhere."""
    p = owl.readConfig(os.path.join("examples", "Case_chris+pat"))
    np.testing.assert_allclose(
        p.tau_kn[:, :3].T,
        CHRIS_PAT_FIRST_YEARS,
        rtol=RTOL,
        err_msg=(
            "A seeded rate series differs from the recorded one. If this fails only on "
            "some platforms, correlated draws have stopped being reproducible across "
            "LAPACK builds; see owlplanner.rate_models._sampling."
        ),
    )


# Identical inputs should give an identical plan, so the objective is pinned too: pinning the
# series alone would not tell us whether it carried through to a result.
#
# The draw depends on the rate model, its window and the seed -- not on the household -- so any
# case can carry it, and the series above is reproduced exactly by every one tried. That matters
# because the case used here decides how noisy the pin is, and Case_chris+pat was a poor choice:
# it is the pool's most oscillation-prone plan, cycling on the Social Security ramp so that the
# loop returns the better of two states. Which state it lands on moves with anything that
# perturbs the arithmetic -- $84 with the MOSEK thread count, $103 between HiGHS builds, and a
# different value on each platform -- so the pin needed a platform-by-solver table and had to be
# re-measured three times in two months, every time telling us about branch-and-bound rather than
# about seeds.
#
# Case_bill carries the same draw and converges monotonically in 2 iterations with a zero
# residual, giving 52,032.45 under HiGHS and MOSEK alike. So the objective is a constant here
# rather than a fixed point that happened to be selected, and one number needs no keying.
BILL_SEEDED_BASIS = 52_032.45


@pytest.mark.toml
def test_a_seeded_series_carries_through_to_a_plan():
    """The series is exact; this checks it reaches the solver and yields the same plan.

    Any case can carry the draw, so this uses one whose answer does not wander: Case_bill is
    monotonic in 2 iterations and agrees between solvers to the cent. A failure here means the
    seeded series stopped reaching the plan, not that branch-and-bound picked differently.
    """
    solver = "MOSEK" if os.getenv("OWL_TEST_SOLVER", "").lower() == "mosek" else "HiGHS"
    p = owl.readConfig(os.path.join("examples", "Case_bill"))
    p.setReproducible(True, seed=2026)
    p.setRates("historical_lognormal", frm=1928, to=2025)
    p.solverOptions["solver"] = solver
    p.resolve()
    assert p.caseStatus == "solved"
    np.testing.assert_allclose(p.tau_kn[:, :3].T, CHRIS_PAT_FIRST_YEARS, rtol=RTOL,
                               err_msg="the seeded draw is not reproduced when another case carries it")
    assert p.basis == pytest.approx(BILL_SEEDED_BASIS, rel=5e-4, abs=50)


@pytest.mark.toml
def test_the_shipped_stochastic_case_still_solves():
    """Case_chris+pat is the one shipped example that draws its returns, so it must still solve.

    Its objective is deliberately not pinned: see the note above. This keeps the end-to-end
    coverage -- a stochastic case loading, drawing and solving -- without pinning a number that
    moves for reasons unrelated to the seed.
    """
    p = owl.readConfig(os.path.join("examples", "Case_chris+pat"))
    p.resolve()
    assert p.caseStatus == "solved"
    assert p.basis > 0


@pytest.mark.toml
def test_seeded_case_is_stable_across_loads():
    """Same seed, same series, within a single machine."""
    series = []
    for _ in range(2):
        p = owl.readConfig(os.path.join("examples", "Case_chris+pat"))
        series.append(p.tau_kn.copy())
    np.testing.assert_array_equal(series[0], series[1])


def test_draw_is_independent_of_the_factorization():
    """The helper must not inherit whichever factorization numpy would have chosen.

    This is the mechanism itself: the same seed and covariance under three equally
    valid factorizations give three unrelated draws, and only one of them is unique.
    """
    mean = np.zeros(4)
    cov = np.array(
        [
            [0.0377, 0.0060, 0.0003, 0.0006],
            [0.0060, 0.0059, 0.0040, -0.0004],
            [0.0003, 0.0040, 0.0062, -0.0003],
            [0.0006, -0.0004, -0.0003, 0.0015],
        ]
    )
    drawn = _sampling.multivariate_normal(np.random.default_rng(2026), mean, cov, size=1)
    expected = np.random.default_rng(2026).multivariate_normal(mean, cov, size=1, method="cholesky")
    np.testing.assert_allclose(drawn, expected, rtol=1e-12)

    # And it is genuinely a different answer from the default, which is the whole point.
    svd = np.random.default_rng(2026).multivariate_normal(mean, cov, size=1, method="svd")
    assert not np.allclose(drawn, svd)


def test_singular_covariance_falls_back_with_a_warning():
    """A covariance that cannot be factorized this way must still produce a draw."""
    singular = np.array([[1.0, 1.0], [1.0, 1.0]])
    with pytest.warns(RuntimeWarning, match="not positive definite"):
        out = _sampling.multivariate_normal(np.random.default_rng(0), np.zeros(2), singular, size=3)
    assert out.shape == (3, 2)
    # A singular covariance of this form makes both components equal, to the accuracy
    # the fallback factorization affords.
    np.testing.assert_allclose(out[:, 0], out[:, 1], rtol=1e-6)
