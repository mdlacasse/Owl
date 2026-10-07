"""
A bracket charged by MAGI applies above its threshold, not at it.

The binary formulations of IRMAA and ACA select a bracket q and bound its MAGI portion by
L_{q-1} z_q <= h_q <= L_q z_q. With those bounds a MAGI sitting exactly on a threshold fits both
neighbouring brackets, and the solver could charge the higher one. It normally would not, but
where the plan's money is worth almost nothing to the objective (a first spouse's assets left to
non-spouse heirs, only the final bequest counted) nothing stopped it: Case_alex+jamie with
Medicare and ACA exact was charged $622 of IRMAA its own MAGI did not owe (MOSEK), and
Case_avery+quinn $21,812. Each higher bracket now starts BRACKET_MARGIN above its threshold.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import pathlib
from datetime import date

import numpy as np
import pytest

import owlplanner as owl

_EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"


def _single(name, age, slcsp=0.0):
    thisyear = date.today().year
    p = owl.Plan([name], [f"{thisyear - age}-01-15"], [85], name, verbose=False, logstreams=[io.StringIO()])
    p.setSpendingProfile("flat", 60)
    p.setAccountBalances(taxable=[500], taxDeferred=[1500], taxFree=[200], startDate="1-1")
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setSocialSecurity([2000], [67])
    p.setRates("historical average", 1928, 2025)
    if slcsp:
        p.setACA(slcsp=slcsp)
    return p


def _lower_bound_rows(p, tag_name, z_name):
    """{(nn, q): coefficient on the bracket binary} for every lower-bound row of a family."""
    out = {}
    for r, tag in enumerate(p.A.tags):
        if isinstance(tag, tuple) and tag and tag[0] == tag_name:
            _, nn, q = tag
            zcol = p.vm[z_name].idx(nn, q)
            coef = dict(zip(p.A.Aind[r], p.A.Aval[r]))[zcol]
            out[(nn, q)] = coef
    return out


def test_irmaa_brackets_start_above_their_thresholds():
    p = _single("irmaa", 66)
    p.solve("maxSpending", options={"withMedicare": "optimize", "bequest": 0})
    # More than the dollar of slack the fixed-point residual allows at a threshold, so a plan
    # charged a bracket at its lowest MAGI still reads as that bracket.
    rows = _lower_bound_rows(p, "irmaa_bracket_lb", "zm")
    assert rows, "this plan should build IRMAA lower-bound rows"
    for (nn, q), coef in rows.items():
        margin = -coef - p.Lbar_nq[nn, q - 1]
        if p.nm + nn < 2:
            # Pinned from previousMAGIs: a known MAGI just above a threshold must stay feasible.
            assert margin == pytest.approx(0.0), (nn, q)
        else:
            assert margin > 1.0, f"bracket {q} of year {nn} starts {margin:.2f} above its threshold"
    assert any(p.nm + nn >= 2 for nn, _ in rows), "no row past the pinned years was checked"


def test_aca_brackets_start_above_their_thresholds():
    p = _single("aca", 60, slcsp=12.0)
    p.solve("maxSpending", options={"withACA": "optimize", "bequest": 0})
    rows = _lower_bound_rows(p, "aca_bracket_lb", "za")
    assert rows, "this plan should build ACA lower-bound rows"
    for (nn, r), coef in rows.items():
        margin = -coef - p.Lbar_aca_nr[nn, r - 1]
        assert margin > 1.0, f"bracket {r} of year {nn} starts {margin:.2f} above its threshold"


@pytest.mark.toml
def test_no_year_is_charged_a_bracket_its_magi_does_not_reach():
    """Case_alex+jamie, Medicare and ACA exact: $622 of IRMAA residual before the margin (MOSEK;
    HiGHS happened to pick the cheaper bracket)."""
    p = owl.readConfig(str(_EXAMPLES / "Case_alex+jamie.toml"), verbose=False, logstreams=[io.StringIO()])
    p.solve(p.objective, options={**p.solverOptions, "withMedicare": "optimize", "withACA": "optimize",
                                  "maxTime": 120})
    assert p.caseStatus == "solved"
    res = p._fixedPointResidualByYear(includeMedicare=True)
    for fam in ("IRMAA", "ACA"):
        if fam in res:
            worst = float(np.max(np.abs(res[fam])))
            assert worst < 1.0, f"{fam} charged ${worst:,.2f} more than the plan's MAGI implies in some year"
