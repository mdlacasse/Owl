"""
Tests for NIIT MILP formulation (withNIIT="optimize").

Validates:
- Feasibility: withNIIT='optimize' produces a valid solution.
- J_n is non-negative for all years.
- J_n matches tx.computeNIIT reference.
- 'withNIIT' is in knownOptions.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np
from datetime import date

import owlplanner as owl
from owlplanner import tax2026 as tx

solver = 'HiGHS'


def _make_plan(name, taxable, tax_deferred, tax_free, rate_year=2000,
               n_individuals=2, expectancy=None):
    """Minimal plan for NIIT MILP testing. Balances in thousands."""
    thisyear = date.today().year
    if n_individuals == 2:
        inames = ['Jack', 'Jill']
        dobs = [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"]
        if expectancy is None:
            expectancy = [75, 75]   # Short horizon for fast tests
        alloc = [[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]]
        ss_pias = [2000, 1500]
        ss_ages = [62, 62]
    else:
        inames = ['Jack']
        dobs = [f"{thisyear - 66}-01-15"]
        if expectancy is None:
            expectancy = [75]
        alloc = [[[60, 40, 0, 0], [70, 30, 0, 0]]]
        ss_pias = [2000]
        ss_ages = [62]

    p = owl.Plan(inames, dobs, expectancy, name)
    p.setSpendingProfile('flat', 60)
    p.setAccountBalances(taxable=taxable, taxDeferred=tax_deferred, taxFree=tax_free,
                         startDate="1-1")
    p.setInterpolationMethod('s-curve')
    p.setAllocationRatios('individual', generic=alloc)
    p.setPension([0] * n_individuals, [65] * n_individuals)
    p.setSocialSecurity(ss_pias, ss_ages)
    p.setRates('historical', rate_year)
    return p


class TestNIITMilp:
    """Tests for the NIIT MILP formulation (withNIIT='optimize')."""

    # Use limited iterations to keep tests fast (may not converge for quantities
    # not covered by the optimize options, but verifies NIIT-specific behavior).
    _BASE_OPTS = {
        'solver': solver,
        'withNIIT': 'optimize',
        'withSSTaxability': 'optimize',
        'maxIter': 5,
    }

    def _solve(self, extra_options=None, n_individuals=2):
        """Couple plan (short horizon) solved with NIIT MILP."""
        taxable = [200, 100] if n_individuals == 2 else [200]
        tax_def = [500, 300] if n_individuals == 2 else [500]
        tax_fr = [100, 100] if n_individuals == 2 else [100]
        p = _make_plan('niit_milp', taxable=taxable, tax_deferred=tax_def, tax_free=tax_fr,
                       n_individuals=n_individuals)
        opts = dict(self._BASE_OPTS)
        if extra_options:
            opts.update(extra_options)
        p.solve('maxSpending', opts)
        return p

    def test_niit_milp_feasible(self):
        """withNIIT='optimize' produces a feasible solution."""
        p = self._solve()
        assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"

    def test_niit_milp_nonnegative(self):
        """J_n (NIIT tax) is non-negative for all years."""
        p = self._solve()
        assert p.caseStatus == 'solved'
        assert np.all(p.J_n >= -0.01), f"Negative NIIT in year(s): min={p.J_n.min():.2f}"

    def test_niit_milp_zero_below_threshold(self):
        """J_n == 0 in years where MAGI is clearly below the NIIT threshold."""
        p = self._solve()
        assert p.caseStatus == 'solved'
        for n in range(p.N_n):
            status_n = 0 if n >= p.n_d else p.N_i - 1
            T_niit = 200000.0 if status_n == 0 else 250000.0
            if p.MAGI_n[n] < T_niit - 500:   # 500 slack for rounding
                assert p.J_n[n] < 10.0, (
                    f"Year {n}: J_n={p.J_n[n]:.2f} should be ~0 "
                    f"(MAGI={p.MAGI_n[n]:.0f} < T_niit={T_niit:.0f})"
                )

    def test_niit_milp_matches_reference(self):
        """J_n from MILP matches tx.computeNIIT reference within $200."""
        p = self._solve()
        assert p.caseStatus == 'solved'
        J_ref = tx.computeNIIT(p.N_i, p.MAGI_n, p.I_n, p.Q_n, p.n_d, p.N_n)
        np.testing.assert_allclose(p.J_n, J_ref, atol=200.0,
                                   err_msg="MILP J_n does not match computeNIIT reference")

    def test_niit_milp_with_ltcg_optimize(self):
        """withNIIT='optimize' combined with withLTCG='optimize' is feasible."""
        p = self._solve({'withLTCG': 'optimize'})
        assert p.caseStatus == 'solved', f"Solver status: {p.caseStatus}"
        assert np.all(p.J_n >= -0.01), "Negative NIIT in combined NIIT+LTCG mode"

    def test_niit_known_option(self):
        """'withNIIT' is recognized as a known option (not silently dropped)."""
        import io
        import logging
        p = _make_plan('niit_opt_known', taxable=[100, 50], tax_deferred=[300, 200],
                       tax_free=[50, 50])
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logging.getLogger().addHandler(handler)
        p.solve('maxSpending', {'withNIIT': 'optimize', 'maxIter': 3})
        logging.getLogger().removeHandler(handler)
        output = log_capture.getvalue()
        assert 'withNIIT' not in output or 'Ignoring unknown' not in output
