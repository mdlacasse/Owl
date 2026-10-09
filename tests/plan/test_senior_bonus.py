"""
Tests for the OBBBA 65+ bonus deduction and its MAGI phase-out (withSeniorBonus).

In loop mode the deduction is set from the previous iterate's MAGI, so a solve cannot trade
income against it and can settle on a plan that pays for income the bonus would have sheltered:
pinning the first-year Roth conversion then did better than the unpinned optimum. In optimize
mode the phase-out is part of the LP, with one binary per bonus year for the point where the
bonus is gone.

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
from pathlib import Path

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import tax_federal as tx
from owlplanner.utils import normalize_mode_option

THISYEAR = date.today().year
BONUS_YEARS_LEFT = tx.OBBBA_BONUS_EXPIRATION_YEAR - THISYEAR + 1
needs_bonus_years = pytest.mark.skipif(BONUS_YEARS_LEFT < 1, reason="the OBBBA senior bonus has expired")
CASE_DANA = Path(__file__).resolve().parents[2] / "examples" / "Case_dana.toml"


def test_schedule_single_and_couple():
    yob = THISYEAR - 66
    count, threshold = tx.seniorBonusSchedule([yob], 0, 99, 6)
    years = max(0, BONUS_YEARS_LEFT)
    assert list(count) == [1] * min(years, 6) + [0] * (6 - min(years, 6))
    assert np.all(threshold == tx.bonusThreshold[0])
    # A couple: the younger spouse turns 65 next year and dies in year 2.
    count, threshold = tx.seniorBonusSchedule([THISYEAR - 68, THISYEAR - 64], 1, 2, 4)
    expect = [1, 2, 1, 0][: max(0, BONUS_YEARS_LEFT)] + [0] * max(0, 4 - BONUS_YEARS_LEFT)
    assert list(count) == expect[:4]
    assert list(threshold) == [tx.bonusThreshold[1]] * 2 + [tx.bonusThreshold[0]] * 2


def test_mode_names():
    assert normalize_mode_option("withSeniorBonus", "Optimize") == "optimize"
    assert normalize_mode_option("withSeniorBonus", "none") == "loop"
    with pytest.raises(ValueError, match="withSeniorBonus"):
        normalize_mode_option("withSeniorBonus", "exact")


def _single(taxable, tax_deferred, conversions=None, spending=40):
    p = owl.Plan(["Lee"], [f"{THISYEAR - 66}-03-01"], [80], "bonus", verbose=False)
    p.setAccountBalances(taxable=[taxable], taxDeferred=[tax_deferred], taxFree=[0])
    p.setSocialSecurity([1500], [70])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setSpendingProfile("flat")
    p.setRates("user", values=[6, 4, 4, 2.5])
    if conversions is not None:
        p.rothXfixed_in[0, : len(conversions)] = True
        p.myRothX_in[0, : len(conversions)] = conversions
    return p, {"netSpending": spending, "withSeniorBonus": "optimize", "solver": "HiGHS"}


def _deduction_implied(p):
    return tx.taxParams(p.yobs, p.i_d, p.n_d, p.N_n, p.gamma_n, p.MAGI_n, p.yOBBBA)[0]


@needs_bonus_years
@pytest.mark.parametrize("conversion", [0.0, 60_000.0, 250_000.0])
def test_optimize_mode_charges_the_deduction_its_own_magi_implies(conversion):
    """Below, inside, and past the end of the phase-out (a $250k conversion puts MAGI above $175k)."""
    p, opts = _single(300, 1200, conversions=[conversion])
    p.solve("maxBequest", opts)
    assert p.caseStatus == "solved"
    years = slice(0, min(BONUS_YEARS_LEFT, p.N_n))
    np.testing.assert_allclose(p.sigmaBar_n[years], _deduction_implied(p)[years], atol=1.0)
    assert abs(p.fixedPointResidual["deduction"]["abs_sum"]) < 1.0
    if conversion == 250_000.0:
        assert p.MAGI_n[0] > tx.bonusThreshold[0] + tx.SENIOR_BONUS / tx.SENIOR_BONUS_PHASEOUT_RATE


@needs_bonus_years
def test_breakpoint_preset_includes_the_senior_bonus():
    p, opts = _single(300, 1200)
    opts.pop("withSeniorBonus")
    opts["breakpointMethod"] = "branch-and-bound"
    p.solve("maxBequest", opts)
    assert p.solverOptions["withSeniorBonus"] == "optimize"
    assert "senior bonus" in p.breakpointMethodUsed


@needs_bonus_years
@pytest.mark.toml
def test_pinning_the_first_conversion_no_longer_beats_the_optimum():
    """Case_dana, 1950 returns: in loop mode the pinned plan left $1,283 more than the unpinned one."""
    results = {}
    for pinned in (False, True):
        p = owl.readConfig(str(CASE_DANA), verbose=False, loadHFP=True)
        p.setRates("historical", 1950)
        opts = dict(p.solverOptions)
        opts.pop("bequest", None)
        opts.update(netSpending=58.0, solver="HiGHS", withSeniorBonus="optimize")
        if pinned:
            p.rothXfixed_in[0, 0] = True
            p.myRothX_in[0, 0] = 63_636.0
        p.solve("maxBequest", opts)
        assert p.caseStatus == "solved"
        results[pinned] = p.bequest
    assert results[False] >= results[True] - 1.0
