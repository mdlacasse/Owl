"""
Tests for NIIT MILP formulation (withNIIT="optimize").

Validates:
- Feasibility: withNIIT='optimize' produces a valid solution.
- J_n is non-negative for all years.
- J_n matches tx.computeNIIT reference.
- 'withNIIT' is in knownOptions.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import numpy as np
import pytest
import pathlib
from datetime import date

import owlplanner as owl
from owlplanner import tax_federal as tx


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _make_plan(name, taxable, tax_deferred, tax_free, rate_year=2000, n_individuals=2, expectancy=None):
    """Minimal plan for NIIT MILP testing. Balances in thousands.
    Uses short horizon (expectancy 70) to keep solve time low.
    """
    thisyear = date.today().year
    if n_individuals == 2:
        inames = ["Jack", "Jill"]
        dobs = [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"]
        if expectancy is None:
            expectancy = [70, 70]  # Short horizon for fast tests (N_n=8)
        alloc = [[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]]
        ss_pias = [2000, 1500]
        ss_ages = [62, 62]
    else:
        inames = ["Jack"]
        dobs = [f"{thisyear - 66}-01-15"]
        if expectancy is None:
            expectancy = [70]
        alloc = [[[60, 40, 0, 0], [70, 30, 0, 0]]]
        ss_pias = [2000]
        ss_ages = [62]

    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=taxable, taxDeferred=tax_deferred, taxFree=tax_free, startDate="1-1")
    p.setInterpolationMethod("s-curve")
    p.setAllocationRatios("individual", generic=alloc)
    p.setPension([0] * n_individuals, [65] * n_individuals)
    p.setSocialSecurity(ss_pias, ss_ages)
    p.setRates("historical", rate_year)
    return p


def _solve_base(extra_options=None, n_individuals=2):
    """Solve once with base NIIT options; used by class-scoped fixture and LTCG test."""
    base_opts = {
        "withNIIT": "optimize",
        "withSSTaxability": "optimize",
        "maxIter": 2,
    }
    taxable = [200, 100] if n_individuals == 2 else [200]
    tax_def = [500, 300] if n_individuals == 2 else [500]
    tax_fr = [100, 100] if n_individuals == 2 else [100]
    p = _make_plan("niit_milp", taxable=taxable, tax_deferred=tax_def, tax_free=tax_fr, n_individuals=n_individuals)
    opts = dict(base_opts)
    if extra_options:
        opts.update(extra_options)
    p.solve("maxSpending", opts)
    return p


@pytest.fixture(scope="class")
def solved_plan():
    """One shared solve for tests that only need a feasible NIIT MILP solution."""
    return _solve_base()


class TestNIITMilp:
    """Tests for the NIIT MILP formulation (withNIIT='optimize')."""

    # Use few iterations and short horizon to keep tests fast.
    _BASE_OPTS = {
        "withNIIT": "optimize",
        "withSSTaxability": "optimize",
        "maxIter": 2,
    }

    def _solve(self, extra_options=None, n_individuals=2):
        """Couple plan (short horizon) solved with NIIT MILP."""
        return _solve_base(extra_options=extra_options, n_individuals=n_individuals)

    def test_niit_milp_feasible(self, solved_plan):
        """withNIIT='optimize' produces a feasible solution."""
        p = solved_plan
        assert p.caseStatus == "solved", f"Solver status: {p.caseStatus}"

    def test_niit_milp_nonnegative(self, solved_plan):
        """J_n (NIIT tax) is non-negative for all years."""
        p = solved_plan
        assert p.caseStatus == "solved"
        assert np.all(p.J_n >= -0.01), f"Negative NIIT in year(s): min={p.J_n.min():.2f}"

    def test_niit_milp_zero_below_threshold(self, solved_plan):
        """J_n == 0 in years where MAGI is clearly below the NIIT threshold."""
        p = solved_plan
        assert p.caseStatus == "solved"
        for n in range(p.N_n):
            status_n = 0 if n >= p.n_d else p.N_i - 1
            T_niit = 200000.0 if status_n == 0 else 250000.0
            if p.MAGI_n[n] < T_niit - 500:  # 500 slack for rounding
                assert p.J_n[n] < 10.0, (
                    f"Year {n}: J_n={p.J_n[n]:.2f} should be ~0 (MAGI={p.MAGI_n[n]:.0f} < T_niit={T_niit:.0f})"
                )

    def test_niit_milp_matches_reference(self, solved_plan):
        """J_n from MILP matches tx.computeNIIT reference within $200."""
        p = solved_plan
        assert p.caseStatus == "solved"
        J_ref = tx.computeNIIT(p.N_i, p.MAGI_n, p.I_n, p.Q_n, p.n_d, p.N_n)
        np.testing.assert_allclose(p.J_n, J_ref, atol=200.0, err_msg="MILP J_n does not match computeNIIT reference")

    def test_niit_milp_with_ltcg_optimize(self):
        """withNIIT='optimize' combined with withLTCG='optimize' is feasible."""
        p = self._solve({"withLTCG": "optimize"})
        assert p.caseStatus == "solved", f"Solver status: {p.caseStatus}"
        assert np.all(p.J_n >= -0.01), "Negative NIIT in combined NIIT+LTCG mode"

    def test_niit_nii_cap_never_exceeded(self):
        """J_n never exceeds 0.038 * NII_n (IRS NII cap) — exercises high-ordinary-income case.

        Large tax-deferred / small taxable forces MAGI-T >> NII in some years.
        The NII cap (niis surplus variable) must reduce J_n below 0.038*(MAGI-T).
        """
        # Dominating IRA balance → large RMDs → G_n drives MAGI above $250k threshold.
        # Tiny taxable account → Q_n is small → NII cap binds.
        p = _make_plan("niit_nii_cap", taxable=[20, 10], tax_deferred=[3000, 2000], tax_free=[50, 50])
        p.solve(
            "maxSpending",
            {
                "withNIIT": "optimize",
                "withSSTaxability": "loop",
                "maxIter": 3,
            },
        )
        assert p.caseStatus == "solved"

        nii_n = p.I_n + p.Q_n
        for n in range(p.N_n):
            assert p.J_n[n] <= 0.038 * max(0.0, nii_n[n]) + 1.0, (
                f"Year {n}: J_n={p.J_n[n]:.2f} exceeds 0.038*NII={0.038 * nii_n[n]:.2f} (MAGI={p.MAGI_n[n]:.0f})"
            )

        # Verify the fix is exercised: at least one year where MAGI > threshold and NII < MAGI-T.
        any_capped = False
        for n in range(p.N_n):
            status_n = 0 if n >= p.n_d else p.N_i - 1
            T_niit = 200000.0 if status_n == 0 else 250000.0
            if p.MAGI_n[n] > T_niit and nii_n[n] < p.MAGI_n[n] - T_niit - 1.0:
                any_capped = True
                break
        assert any_capped, "Test scenario did not produce a year where the NII cap binds"

        # Cross-check against the reference formula.
        J_ref = tx.computeNIIT(p.N_i, p.MAGI_n, p.I_n, p.Q_n, p.n_d, p.N_n)
        np.testing.assert_allclose(p.J_n, J_ref, atol=200.0, err_msg="MILP J_n does not match computeNIIT with NII cap")

    def test_niit_known_option(self):
        """'withNIIT' is recognized as a known option (not silently dropped)."""
        import io
        import logging

        p = _make_plan("niit_opt_known", taxable=[100, 50], tax_deferred=[300, 200], tax_free=[50, 50])
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logging.getLogger().addHandler(handler)
        p.solve("maxSpending", {"withNIIT": "optimize", "maxIter": 3})
        logging.getLogger().removeHandler(handler)
        output = log_capture.getvalue()
        assert "withNIIT" not in output or "Ignoring unknown" not in output

    def test_niit_optimize_vs_loop_spending(self):
        """withNIIT='optimize' spending within 2% of SC-loop and J_n matches reference."""
        common = {"withSSTaxability": "loop", "withMedicare": "loop", "maxIter": 5}
        p_loop = _make_plan("niit_loop", taxable=[200, 100], tax_deferred=[500, 300], tax_free=[100, 100])
        p_loop.solve("maxSpending", {**common, "withNIIT": "loop"})
        p_opt = _make_plan("niit_opt", taxable=[200, 100], tax_deferred=[500, 300], tax_free=[100, 100])
        p_opt.solve("maxSpending", {**common, "withNIIT": "optimize"})
        assert p_loop.caseStatus == "solved"
        assert p_opt.caseStatus == "solved"
        rel_diff = abs(p_opt.g_n[0] - p_loop.g_n[0]) / max(abs(p_loop.g_n[0]), 1)
        assert rel_diff < 0.02, (
            f"NIIT optimize spending {p_opt.g_n[0]:.0f} differs from loop {p_loop.g_n[0]:.0f} by {100 * rel_diff:.2f}%"
        )
        # Optimizer's J_n must match the IRS reference formula (not just the loop plan's J_n).
        J_ref_opt = tx.computeNIIT(
            p_opt.N_i,
            p_opt.MAGI_n,
            p_opt.I_n,
            p_opt.Q_n,
            p_opt.n_d,
            p_opt.N_n,
        )
        np.testing.assert_allclose(p_opt.J_n, J_ref_opt, atol=200.0)

    def test_niit_optimize_large_taxable_J_n_vs_reference(self):
        """withNIIT='optimize' J_n matches reference when taxable account is large (large Q_n).

        Regression test for a bug where the MAGI LP constraint omitted Q_n (LTCG capital gains)
        because the portfolio LP expression and q bracket variables cancelled at the partition
        minimum, making J_n = 0.038*I_n instead of 0.038*min(MAGI-T, I_n+Q_n).
        """
        # Large taxable account → large Q_n → NII-cap binding in several years.
        p = _make_plan("niit_large_taxable", taxable=[1000, 100], tax_deferred=[500, 300], tax_free=[50, 50])
        p.solve(
            "maxSpending",
            {
                "withNIIT": "optimize",
                "withLTCG": "optimize",
                "withSSTaxability": "loop",
                "withMedicare": "loop",
                "maxIter": 4,
            },
        )
        assert p.caseStatus == "solved"
        J_ref = tx.computeNIIT(p.N_i, p.MAGI_n, p.I_n, p.Q_n, p.n_d, p.N_n)
        np.testing.assert_allclose(
            p.J_n,
            J_ref,
            atol=500.0,
            err_msg="NIIT optimize J_n does not match reference with large taxable account",
        )


@pytest.mark.toml
def test_niit_toml_joe_large_ira_reference():
    """Example TOML (Joe, $650k tax-deferred): loop NIIT matches IRS reference and NII cap."""
    exdir = os.path.join(_REPO_ROOT, "examples")
    case = os.path.join(exdir, "Case_joe.toml")
    hfp = os.path.join(exdir, "HFP_joe.xlsx")
    p = owl.readConfig(case)
    p.readHFP(hfp)
    p.resolve()
    assert p.caseStatus == "solved"
    assert float(np.sum(p.J_n)) > 0.0
    nii_n = p.I_n + p.Q_n
    for n in range(p.N_n):
        assert p.J_n[n] <= 0.038 * max(0.0, nii_n[n]) + 1.0, (
            f"Year {n}: J_n={p.J_n[n]:.2f} exceeds 0.038*NII={0.038 * nii_n[n]:.2f}"
        )
    J_ref = tx.computeNIIT(p.N_i, p.MAGI_n, p.I_n, p.Q_n, p.n_d, p.N_n)
    np.testing.assert_allclose(p.J_n, J_ref, atol=200.0, err_msg="TOML loop NIIT J_n vs computeNIIT")


@pytest.mark.toml
def test_niit_optimize_joe_fixed_asset_capital_gains():
    """withNIIT='optimize' J_n matches reference for Joe's case which has fixed-asset capital gains.

    Regression guard for the MAGI LP constraint: the partition constraint lower bound includes
    fixed_assets_capital_gains_n, so q[0]+q[1]+q[2] at the minimum already captures fixed-asset
    CG. This test confirms that path is exercised and J_n is correct.
    """
    exdir = os.path.join(_REPO_ROOT, "examples")
    case = os.path.join(exdir, "Case_joe.toml")
    hfp = os.path.join(exdir, "HFP_joe.xlsx")
    p = owl.readConfig(case)
    p.readHFP(hfp)
    p.solve(
        "maxSpending",
        {
            "withNIIT": "optimize",
            "withSSTaxability": "loop",
            "withMedicare": "loop",
            "maxIter": 5,
        },
    )
    assert p.caseStatus == "solved"
    assert float(np.sum(p.fixed_assets_capital_gains_n)) > 0.0, (
        "Test requires non-zero fixed-asset capital gains to exercise the MAGI partition path"
    )
    J_ref = tx.computeNIIT(p.N_i, p.MAGI_n, p.I_n, p.Q_n, p.n_d, p.N_n)
    np.testing.assert_allclose(p.J_n, J_ref, atol=200.0, err_msg="NIIT optimize J_n vs reference with fixed-asset CG")


def test_niit_benders_J_n_vs_monolithic():
    """Benders and monolithic agree on J_n when withNIIT=optimize (high-IRA scenario)."""
    gap = 2e-3
    opts = {
        "withNIIT": "optimize",
        "withSSTaxability": "loop",
        "withMedicare": "loop",
        "maxIter": 5,
        "gap": gap,
    }
    balances = dict(taxable=[20, 10], tax_deferred=[3000, 2000], tax_free=[50, 50])
    p_mono = _make_plan("niit_bend_mono", **balances)
    p_mono.solve("maxSpending", opts)
    p_bend = _make_plan("niit_bend_bend", **balances)
    p_bend.solve("maxSpending", {**opts, "withDecomposition": "benders"})
    assert p_mono.caseStatus == "solved"
    assert p_bend.caseStatus == "solved"
    assert float(np.sum(p_mono.J_n)) > 0.0
    np.testing.assert_allclose(p_bend.J_n, p_mono.J_n, atol=1.0, rtol=0.01)
