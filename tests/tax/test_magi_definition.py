"""
The LP's MAGI must be the MAGI the plan reports.

MAGI is defined once, in the formulation: G_n + Q_n + e_n, where G_n is taxable ordinary
income after the standard exemption, so adding e_n back recovers AGI. The optimize modes
decompose that figure into bracket portions, and owl.tex requires the portions to sum to
it exactly -- Eq. (MedDecomp) for IRMAA, and its counterpart for ACA.

Those two rows once built MAGI from raw income components, which already include the
exemption, and then subtracted e as well. MAGI came out one exemption too high, so the
optimizer treated a year as being at the edge of a bracket while the real figure was
$12k-$22k below it, and declined conversions that would have fit. Loop mode was never
affected: it reads MAGI_n directly.

The identity is asserted rather than the premium, because it is the thing the formulation
states and the thing that broke. A bracket only moves when the error happens to straddle a
threshold, so a premium check would have passed for years while the definition was wrong.

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

from datetime import date

import numpy as np
import pytest

import owlplanner as owl

# Rows are built to the cent, and roundCents is applied to the solution.
TOL = 0.05


def _single(name, taxable, tax_deferred, tax_free, age=66, expectancy=80):
    thisyear = date.today().year
    p = owl.Plan([name], [f"{thisyear - age}-01-15"], [expectancy], name, verbose=False)
    p.setVerbose(False)
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[taxable], taxDeferred=[tax_deferred], taxFree=[tax_free], startDate="1-1")
    p.setInterpolationMethod("s-curve")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setPension([0], [65])
    p.setSocialSecurity([2000], [67])
    p.setRates("historical average", 1928, 2025)
    return p


def test_irmaa_brackets_sum_to_the_reported_magi():
    """Eq. (MedDecomp): the bracket portions sum to MAGI two years prior."""
    p = _single("irmaa", 500, 1500, 200)
    p.solve("maxSpending", options={"withMedicare": "optimize", "bequest": 0})
    assert "h" in p.vm, "this plan should build IRMAA bracket variables"

    for nn in range(p.h_qn.shape[0]):
        n2 = p.nm + nn - 2
        if n2 < 0:
            continue  # pinned to the user-supplied previousMAGIs instead
        assert np.sum(p.h_qn[nn, :]) == pytest.approx(p.MAGI_n[n2], abs=TOL), (
            f"year {p.nm + nn}: the LP's MAGI differs from the reported MAGI by "
            f"{np.sum(p.h_qn[nn, :]) - p.MAGI_n[n2]:,.2f}; if that equals the standard "
            f"exemption e_n[{n2}] = {p.e_n[n2]:,.2f}, it has been added twice"
        )


def test_aca_brackets_sum_to_the_reported_magi():
    """The ACA counterpart, on its full-Social-Security MAGI variant."""
    p = _single("aca", 400, 900, 200, age=60, expectancy=80)
    p.setACA(slcsp=12.0)
    p.solve("maxSpending", options={"withACA": "optimize", "bequest": 0})
    assert "haca" in p.vm, "this plan should build ACA bracket variables"

    for nn in range(p.haca_qn.shape[0]):
        assert np.sum(p.haca_qn[nn, :]) == pytest.approx(p.MAGI_aca_n[nn], abs=TOL), (
            f"year {nn}: the LP's ACA MAGI differs from the reported one by "
            f"{np.sum(p.haca_qn[nn, :]) - p.MAGI_aca_n[nn]:,.2f}; if that equals the "
            f"standard exemption e_n[{nn}] = {p.e_n[nn]:,.2f}, it has been added twice"
        )


def test_reported_magi_is_agi():
    """MAGI_n = G_n + Q_n + e_n, the definition everything else is measured against."""
    p = _single("agi", 500, 1500, 200)
    p.solve("maxSpending", options={"bequest": 0})
    np.testing.assert_allclose(p.MAGI_n, p.G_n + p.Q_n + p.e_n, atol=TOL)
