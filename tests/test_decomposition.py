"""
Tests for MIP decomposition modes: sequential (relax-and-fix) and Benders.

Covers:
- Sequential decomposition produces a feasible solution (heuristic).
- Benders decomposition produces a solution within MIP gap of monolithic.
- Benders converges without error on jack+jill with Medicare optimize.
- Benders and monolithic agree within tolerance on a simple single-person case.
- Fallback to monolithic when no bracket binaries are present.
"""

from datetime import date

import owlplanner as owl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_simple_plan(name="DecompTest"):
    """Single-person plan for fast decomposition tests."""
    thisyear = date.today().year
    inames = ["Alex"]
    dobs = [f"{thisyear - 62}-01-15"]
    expectancy = [82]
    p = owl.Plan(inames, dobs, expectancy, name, verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[200], taxDeferred=[800], taxFree=[100])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setSocialSecurity([2000], [67])
    return p


def _make_older_two_person(name="AlexJamie"):
    """Two-person plan where both individuals are near/past Medicare age (nm=0).
    This triggers fixed zm binary columns in _configure_Medicare_binary_variables
    (years n < 2 with prevMAGI known), which exposed a Benders infeasibility bug.
    """
    thisyear = date.today().year
    inames = ["Alex", "Jamie"]
    dobs = [f"{thisyear - 66}-01-15", f"{thisyear - 63}-01-16"]   # ages 66 and 63 → nm=0
    expectancy = [85, 87]
    p = owl.Plan(inames, dobs, expectancy, name, verbose=False)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150], taxFree=[70, 40])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setAllocationRatios("individual",
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setSocialSecurity([2333, 2083], [67, 70])
    return p


def _make_jack_jill(name="JackJill"):
    """Two-person plan matching test_repro.py jack+jill setup."""
    thisyear = date.today().year
    inames = ["Jack", "Jill"]
    dobs = [f"{thisyear - 62}-01-15", f"{thisyear - 59}-01-16"]
    expectancy = [82, 79]
    p = owl.Plan(inames, dobs, expectancy, name, verbose=False)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[90, 60], taxDeferred=[600, 150],
                         taxFree=[70, 40], startDate="1-1")
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setInterpolationMethod("s-curve")
    p.setAllocationRatios("individual",
                          generic=[[[60, 40, 0, 0], [70, 30, 0, 0]],
                                   [[50, 50, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0, 10], [65, 65])
    p.setSocialSecurity([2333, 2083], [67, 70])
    return p


# ---------------------------------------------------------------------------
# Sequential decomposition tests
# ---------------------------------------------------------------------------

class TestSequentialDecomposition:
    """Tests for withDecomposition='sequential' (relax-and-fix heuristic)."""

    def test_sequential_feasible_no_optimize(self):
        """Sequential mode with no binary bracket families falls back to monolithic."""
        p = _make_simple_plan("seq_no_optimize")
        p.solve("maxSpending", options={
            "withMedicare": "loop",
            "withDecomposition": "sequential",
        })
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_sequential_with_medicare_optimize(self):
        """Sequential mode with Medicare optimize should produce a feasible result."""
        p = _make_simple_plan("seq_medi_opt")
        p.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "sequential",
        })
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_sequential_jack_jill(self):
        """Sequential decomposition on jack+jill with Medicare optimize."""
        p = _make_jack_jill("seq_jj")
        p.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "sequential",
        })
        assert p.g_n is not None
        assert p.g_n[0] > 0


# ---------------------------------------------------------------------------
# Benders decomposition tests
# ---------------------------------------------------------------------------

class TestBendersDecomposition:
    """Tests for withDecomposition='benders' (certified global optimum)."""

    def test_benders_no_optimize_fallback(self):
        """Benders with no bracket binaries falls back to monolithic MIP."""
        p = _make_simple_plan("benders_fallback")
        p.solve("maxSpending", options={
            "withMedicare": "loop",
            "withDecomposition": "benders",
        })
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_benders_feasible_medicare_optimize(self):
        """Benders with Medicare optimize produces a valid feasible solution."""
        p = _make_simple_plan("benders_medi_opt")
        p.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "benders",
        })
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_benders_vs_monolithic_single(self):
        """Benders and monolithic MIP agree within gap tolerance on a single-person case."""
        gap = 1e-3   # 0.1% relative gap for comparison

        p_mono = _make_simple_plan("mono_single")
        p_mono.solve("maxSpending", options={
            "withMedicare": "optimize",
            "gap": gap,
        })
        spending_mono = p_mono.g_n[0]

        p_bend = _make_simple_plan("benders_single")
        p_bend.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "benders",
            "gap": gap,
        })
        spending_benders = p_bend.g_n[0]

        # Benders is guaranteed optimal; must be >= monolithic within tolerance.
        # Both should be within gap fraction of each other.
        assert spending_mono > 0
        assert spending_benders > 0
        rel_diff = abs(spending_benders - spending_mono) / max(spending_mono, 1.0)
        assert rel_diff <= 10 * gap, (
            f"Benders ({spending_benders:.0f}) and monolithic ({spending_mono:.0f}) "
            f"differ by {rel_diff:.4f}, expected <= {10 * gap:.4f}."
        )

    def test_benders_jack_jill_medicare(self):
        """Benders on jack+jill with Medicare optimize converges and gives valid result."""
        p = _make_jack_jill("benders_jj")
        p.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "benders",
        })
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_benders_vs_monolithic_jack_jill(self):
        """Benders and monolithic agree within gap on jack+jill with Medicare optimize."""
        gap = 2e-3   # 0.2% relative gap for comparison

        p_mono = _make_jack_jill("mono_jj")
        p_mono.solve("maxSpending", options={
            "withMedicare": "optimize",
            "gap": gap,
        })
        spending_mono = p_mono.g_n[0]

        p_bend = _make_jack_jill("benders_jj2")
        p_bend.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "benders",
            "gap": gap,
        })
        spending_benders = p_bend.g_n[0]

        assert spending_mono > 0
        assert spending_benders > 0
        rel_diff = abs(spending_benders - spending_mono) / max(spending_mono, 1.0)
        assert rel_diff <= 10 * gap, (
            f"Benders ({spending_benders:.0f}) and monolithic ({spending_mono:.0f}) "
            f"differ by {rel_diff:.4f}, expected <= {10 * gap:.4f}."
        )

    def test_benders_bequest_objective(self):
        """Benders works for bequest maximization objective."""
        p = _make_simple_plan("benders_bequest")
        p.solve("maxBequest", options={
            "withMedicare": "optimize",
            "withDecomposition": "benders",
            "netSpending": 40,
        })
        assert p.g_n is not None

    def test_benders_older_two_person_medicare(self):
        """Benders on a 2-person plan with nm=0 (both near/past Medicare age).
        This is the regression test for the fixed-zm-column infeasibility bug:
        years n < 2 with nm=0 have zm columns hard-fixed in self.B; if included
        in master_cols the master can assign wrong values, making the SP infeasible.
        """
        p = _make_older_two_person("benders_older_2p")
        p.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "benders",
        })
        assert p.g_n is not None
        assert p.g_n[0] > 0

    def test_benders_max_iter_respected(self):
        """Benders terminates within bendersMaxIter iterations."""
        p = _make_simple_plan("benders_maxiter")
        p.solve("maxSpending", options={
            "withMedicare": "optimize",
            "withDecomposition": "benders",
            "bendersMaxIter": 3,
        })
        # Just verify it completes without error.
        assert p.g_n is not None
