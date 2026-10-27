"""
Tests for applying the SSA earnings test to the plan.

Properties, on the shipped examples:

- with no earnings the streams are exactly those without the test ("without the test"
  below is the test run on zero earnings, see ``_without_the_test``);
- the three examples that pay Social Security before FRA in a year with wages
  above the exempt amount (jack+jill and chris+pat in 2028, alex+jamie in 2026-2027) show
  the withholding, the ARF that replaces it at FRA, and taxes on the *net* benefit;
- the other fifteen are a no-op to the cent;
- a second solve after editing wages sees the new earnings;
- the outputs reach the Summary and the worksheet, ``owlcli explain`` reports both of
  them, and the solve warns (once) where the test cannot be right.

Expected values are hand numbers from the primary rules — 20 CFR 404.410 reduction rates
(5/9 of 1% for each of the first 36 months before FRA, 5/12 of 1% beyond) and the 2026
exempt amounts of POMS RS 02501.025 D — not from the code under test. Streams are in
today's dollars, as `zeta_in` is. Checks are paid one month in arrears, so a payment year
carries the December check of the year before.

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

import contextlib
import datetime
import glob
import io
import os
import sys

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import socialsecurity as ss
from owlplanner.export import build_summary_dic
from owlplanner.mylogging import Logger

# Frozen plan start (tests/conftest.py freezes the date; keep this in step with it).
THISYEAR = 2026

_EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")

# The three examples that pay SS before FRA in a year with wages above the
# exempt amount (jack+jill and chris+pat: the second spouse's last work year 2028;
# alex+jamie: 2026-2027).
THE_THREE = ["alex+jamie", "chris+pat", "jack+jill"]


# Reduction factor of a benefit claimed `months` months before FRA 67, from the rates of
# 20 CFR 404.410 (5/9 of 1% per month for the first 36 months, 5/12 of 1% beyond).
def _factor(months):
    early = min(months, 36) * 5.0 / 9.0 + max(months - 36, 0) * 5.0 / 12.0
    return 1.0 - early / 100.0


def _hfp_for(case):
    """The example's workbook, or None (Case_bill ships without one)."""
    name = case.replace("Case_", "HFP_").replace("-spending", "").replace("-bequest", "")
    path = os.path.join(_EXAMPLES, name + ".xlsx")
    return path if os.path.exists(path) else None


def _load(case):
    p = owl.readConfig(
        os.path.join(_EXAMPLES, "Case_" + case + ".toml"), verbose=False, logstreams=[io.StringIO()]
    )
    hfp = _hfp_for(case)
    if hfp is not None:
        p.readHFP(hfp)
    return p


@contextlib.contextmanager
def _without_the_test():
    """Owl without the earnings test, for comparisons: the test run on zero earnings
    withholds nothing, so the plan keeps compute_social_security_benefits' streams. Wages
    still count everywhere else (income, taxes)."""
    real = ss.earnings_test

    def zero(*a, **k):
        a = list(a)
        a[8] = np.zeros_like(np.asarray(a[8], dtype=float))
        return real(*a, **k)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ss, "earnings_test", zero)
        yield


def _solve(p, test_on=True):
    """Resolve the plan, with the earnings test or (test_on=False) without it."""
    with contextlib.nullcontext() if test_on else _without_the_test():
        p.resolve()
    assert p.caseStatus == "solved"
    return p


def _n(p, year):
    """Plan-year index of a calendar year."""
    return int(year) - int(p.year_n[0])


def _both_alives(p):
    """Plan-year indices where both spouses are alive (before the first death)."""
    return range(int(np.min(p.horizons)))


# --------------------------------------------------------------------------------------
# No-op: no earnings
# --------------------------------------------------------------------------------------


def test_no_earnings_is_a_no_op():
    """Earnings are what the test reads: with none of them, it changes nothing."""
    p = _load("jack+jill")
    base, _ = ss.compute_social_security_benefits(
        p.ssecAmounts, p.ssecAges, p.yobs, p.mobs, p.tobs, p.horizons, p.N_i, p.N_n
    )
    p.omega_in[:, :] = 0.0
    p.etMonths_in[:, :] = 0.0
    _solve(p, test_on=True)
    assert np.allclose(p.zeta_in, base, rtol=0.0, atol=1e-6)
    assert np.all(p.ss_withheld_in == 0)


def _other_examples():
    cases = []
    for path in sorted(glob.glob(os.path.join(_EXAMPLES, "Case_*.toml"))):
        case = os.path.basename(path)[len("Case_") : -len(".toml")]
        if case not in THE_THREE:
            cases.append(case)
    assert len(cases) == 16  # an empty glob would make the test below check nothing
    return cases


@pytest.mark.parametrize("case", _other_examples())
def test_no_op_objective_on_the_other_examples(case):
    """No-op on the other sixteen examples, objective identical to the cent. Nobody there claims
    before FRA in a year with wages above the exempt amount, except Riley (riley+casey), who
    claims in July after six months of work: the grace year pays every month of entitlement."""
    off = _solve(_load(case), test_on=False)
    on = _solve(_load(case), test_on=True)
    assert round(float(on.basis), 2) == round(float(off.basis), 2)
    assert round(float(on.bequest), 2) == round(float(off.bequest), 2)
    assert np.allclose(on.zeta_in, off.zeta_in, rtol=0.0, atol=1e-6)
    assert np.all(on.ss_withheld_in == 0)
    assert np.all(on.ss_arf_months_i == 0)


# --------------------------------------------------------------------------------------
# The three examples with the test on
# --------------------------------------------------------------------------------------


def test_jack_jill_2028_is_fully_withheld():
    """jack+jill: Jill (born 1966-01, claims 62y1m in Feb 2028) earns $85k in 2028, her
    last work year. The excess ((85,000 - 24,480)/2, before deflating) is larger than the
    whole year's benefit, so every month of her 2028 is withheld and comes back through
    the ARF at FRA (2033)."""
    p = _solve(_load("jack+jill"), test_on=True)
    assert p.zeta_in[1, _n(p, 2028)] == 0.0
    assert p.ss_withheld_in[1, _n(p, 2028)] > 0
    # 11 crediting months: her entitlement months Feb-Dec 2028 (62y1m from Jan 1966).
    assert p.ss_arf_months_i[1] == 11
    assert p.ss_arf_months_spousal_i[1] == 0
    # From FRA: PIA x the factor at the claiming age plus 11 months = 63 exactly,
    # i.e. 48 reduction months (59 at 62y1m less 11 credited): _factor(48) = 0.75.
    from_fra = 12.0 * 1642.0 * _factor(48)
    for n in _both_alives(p):
        if n >= _n(p, 2034):
            assert p.zeta_in[1, n] == pytest.approx(from_fra)


def test_jack_jill_2028_is_partly_spared_with_six_months():
    """The grace year (404.435): with `months worked` 6 the months after June are
    non-service months and are paid whatever the annual excess. The five worked months of
    her entitlement (Feb-Jun) are still withheld."""
    p = _load("jack+jill")
    p.etMonths_in[1, _n(p, 2028)] = 6.0
    _solve(p, test_on=True)
    # Five checks paid in 2028 (entitlement Jul-Nov 2028), the five worked months withheld.
    paid = 5.0 * 1642.0 * _factor(59)
    assert p.zeta_in[1, _n(p, 2028)] == pytest.approx(paid)
    assert p.ss_arf_months_i[1] == 5
    # From FRA: 54 reduction months left (59 less 5 credited) -> 0.725.
    from_fra = 12.0 * 1642.0 * _factor(54)
    for n in _both_alives(p):
        if n >= _n(p, 2034):
            assert p.zeta_in[1, n] == pytest.approx(from_fra)


def test_jack_jill_taxes_on_ss_follow_the_net():
    """Taxes on Social Security are computed from what is paid: the taxable share in 2028
    is zero with the test on (nothing is paid there) and positive without it."""
    off = _solve(_load("jack+jill"), test_on=False)
    on = _solve(_load("jack+jill"), test_on=True)
    n28 = _n(off, 2028)
    taxable_off = float(off.Psi_n[n28] * np.sum(off.zetaBar_in[:, n28]))
    taxable_on = float(on.Psi_n[n28] * np.sum(on.zetaBar_in[:, n28]))
    assert taxable_off > 0
    assert taxable_on == 0.0


def test_chris_pat_2028_is_fully_withheld():
    """chris+pat: Pat (born 1966-01, claims 62y1m in Feb 2028) earns $85k in 2028, the
    last work year; Chris claims at 70 and never meets the test. No spousal add-on for
    either (0.5 x the other PIA is below their own), so the streams are own benefits."""
    p = _solve(_load("chris+pat"), test_on=True)
    assert p.zeta_in[1, _n(p, 2028)] == 0.0
    assert p.ss_arf_months_i[1] == 11
    assert np.all(p.ss_withheld_in[0] == 0)
    from_fra = 12.0 * 1400.0 * _factor(48)
    for n in _both_alives(p):
        if n >= _n(p, 2034):
            assert p.zeta_in[1, n] == pytest.approx(from_fra)


def test_alex_jamie_2026_27_are_fully_withheld():
    """alex+jamie: Jamie (born 1961-01, collecting since 62y1m in 2023) earns $80k in
    2026 and 2027, her last two years before FRA (Jan 2028). Every entitlement month of
    both years is withheld; the one check of 2026 is for December 2025, a pre-plan month
    the test cannot charge. Jamie's spousal add-on only starts with Alex's claim at 69
    (2029), so the years below carry her own benefit alone."""
    p = _solve(_load("alex+jamie"), test_on=True)
    assert p.zeta_in[1, _n(p, 2027)] == 0.0
    assert p.zeta_in[1, _n(p, 2026)] == pytest.approx(1200.0 * _factor(59))
    # Every month of 2026 and 2027 is a crediting month (24); from FRA the factor is the
    # one for 59 - 24 = 35 reduction months.
    assert p.ss_arf_months_i[1] == 24
    # 2028 still carries the December 2027 check, withheld; then 11 checks at FRA.
    assert p.zeta_in[1, _n(p, 2028)] == pytest.approx(11.0 * 1200.0 * _factor(35))


# --------------------------------------------------------------------------------------
# A second solve sees edited wages
# --------------------------------------------------------------------------------------


def test_second_solve_after_editing_wages():
    """The streams are rebuilt at solve time (zeta_in is built before the HFP is read),
    so wages edited between two solves move the test."""
    p = _solve(_load("jack+jill"), test_on=True)
    assert p.zeta_in[1, _n(p, 2028)] == 0.0

    # The UI path: the edited tables are re-read (owlbridge._setContributions).
    tables = {n: p.timeLists[n].copy() for n in p.inames}
    tables["Jill"].loc[tables["Jill"].index[5 + _n(p, 2028)], "anticipated wages"] = 20_000.0
    p.readHFP(tables, houseTables=False)
    _solve(p, test_on=True)
    assert p.zeta_in[1, _n(p, 2028)] > 0  # 20,000 < the 24,480 exempt amount
    assert np.all(p.ss_withheld_in[1] == 0)
    assert p.ss_arf_months_i[1] == 0


# --------------------------------------------------------------------------------------
# Warnings, once per solve
# --------------------------------------------------------------------------------------


def _warn_log(p):
    """A logger for p writing to a buffer; read it with _warn_lines after the solve."""
    buf = io.StringIO()
    p.mylog = Logger(verbose=False, logstreams=[buf])
    return buf


def _warn_lines(buf):
    """The WARNING messages logged into buf."""
    return [line.split(" | ", 3)[-1] for line in buf.getvalue().splitlines() if "| WARNING |" in line]


def test_earnings_are_the_wages_before_pre_tax_deferrals():
    """The test counts wages before pre-tax deferrals (W-2 box 5), and `anticipated wages` are
    the wages in AGI, net of them (#221): in a year with wages, the earnings add back the
    tax-deferred contributions. After-tax ones (taxable, Roth) are already in the wages, and a
    payroll HSA is not box 5. Without wages, a 401k deferral is still earnings, having been paid
    out of wages that all went to it (#229), while an IRA contribution is not (a spousal IRA)."""
    p = _load("chris+pat")
    earnings, months = p._earnings_test_inputs()
    pat, n = 1, int(np.argmax(p.year_n == 2028))
    deferred = p.kappa_ijn[pat, 1, n]
    assert deferred > 0, "test setup: Pat defers in 2028"
    assert earnings[pat, n] == pytest.approx(p.omega_in[pat, n] + deferred)
    assert months[pat, n] == 12
    p.kappa_ijn[pat, 0, n] = 3_000.0  # taxable, from pay: already in the wages
    p.kappa_ijn[pat, 2, n] = 4_000.0  # Roth: already in the wages
    p.kappa_ijn[pat, 3, n] = 5_000.0  # an HSA contribution is not box 5
    assert p._earnings_test_inputs()[0][pat, n] == pytest.approx(p.omega_in[pat, n] + deferred)
    p.omega_in[pat, n] = 0.0
    earnings, months = p._earnings_test_inputs()
    assert p.kappa401k_in[pat, n] == pytest.approx(deferred), "test setup: Pat's deferral is a 401k"
    assert earnings[pat, n] == pytest.approx(deferred) and months[pat, n] == 12
    p.kappa401k_in[pat, n] = 0.0  # the same amount as an IRA contribution
    earnings, months = p._earnings_test_inputs()
    assert earnings[pat, n] == 0.0 and months[pat, n] == 0


def test_jill_is_credited_her_withheld_months():
    """Jill claims at 62y1m and works through 2028: all of 2028 is withheld, and those 11
    months raise her benefit from FRA. Jack claims at 70, past his FRA year: nothing."""
    p = _load("jack+jill")
    _solve(p, test_on=True)
    assert p.ss_arf_months_i[1] == 11
    assert p.ss_arf_months_i[0] == 0


def test_warning_when_a_claiming_age_pays_nothing_before_fra():
    """alex+jamie: every month of Jamie's entitlement before FRA (2026-2027) is withheld,
    so the early claim buys nothing until the ARF at FRA. The warning names the years."""
    p = _load("alex+jamie")
    buf = _warn_log(p)
    _solve(p, test_on=True)
    warned = [w for w in _warn_lines(buf) if "withheld" in w]
    assert len(warned) == 1
    assert "Jamie" in warned[0]
    assert "2026-2027" in warned[0]
    assert "ARF" in warned[0]


# --------------------------------------------------------------------------------------
# Outputs: Summary, worksheet, explain
# --------------------------------------------------------------------------------------


def test_worksheet_column_next_to_ss():
    """The per-person Sources sheet carries 'SS withheld' next to 'social sec', and only
    when something is withheld."""
    on = _solve(_load("jack+jill"), test_on=True)
    wb = on.saveWorkbook(saveToFile=False)
    ws = next(w for w in wb.worksheets if w.title == on.inames[1] + "'s Sources")
    headers = [cell.value for cell in ws[1]]
    assert "SS withheld" in headers
    assert headers.index("SS withheld") == headers.index("social sec") + 1

    off = _solve(_load("jack+jill"), test_on=False)
    wb = off.saveWorkbook(saveToFile=False)
    ws = next(w for w in wb.worksheets if w.title == off.inames[1] + "'s Sources")
    assert "SS withheld" not in [cell.value for cell in ws[1]]


def test_explain_ss_block_gains_both():
    """`owlcli explain` describes the case without solving: it reports what the earnings
    test would withhold at the entered claiming ages."""
    from owlplanner.cli.cmd_explain import _plan_to_explain

    p = _load("jack+jill")
    block = _plan_to_explain(p, "Case_jack+jill.toml", [])["social_security"]
    by_name = {entry["name"]: entry for entry in block}
    jill = by_name["Jill"]["earnings_test"]
    assert jill["arf_months"] == 11
    assert jill["arf_months_spousal"] == 0
    # Every month of 2028 withheld, one month's benefit each (today's $).
    assert jill["ss_withheld_total_today"] == pytest.approx(11 * 1642 * _factor(59), abs=1.0)
    assert by_name["Jack"]["earnings_test"]["arf_months"] == 0
    assert by_name["Jack"]["earnings_test"]["ss_withheld_total_today"] == 0


# --------------------------------------------------------------------------------------
# Warnings under withSSAges, a stop before the claim, the spousal record, units
# --------------------------------------------------------------------------------------


def test_warns_once_under_with_ssages():
    """Under withSSAges the warning fires once: the candidates are many, the user-visible
    solve is one. Alex's age is searched; Jamie's fixed claim pays nothing before FRA."""
    p = _load("alex+jamie")
    buf = _warn_log(p)
    p.solve(p.objective, dict(p.solverOptions or {}, withSSAges=["Alex"]))
    assert p.caseStatus == "solved"
    warned = [w for w in _warn_lines(buf) if "withheld" in w]
    assert len(warned) == 1
    assert "Jamie" in warned[0]


def test_pays_nothing_warning_on_a_fresh_plan_with_a_searched_spouse():
    """Alex's age is searched (and skipped by the warning); Jamie's is fixed and pays
    nothing before FRA. The warning must not depend on a previous solve having built the
    streams: a fresh plan warns like a re-solved one, once per solve."""
    p = _load("alex+jamie")
    buf = _warn_log(p)
    for _ in range(2):
        p.solve(p.objective, dict(p.solverOptions or {}, withSSAges=["Alex"]))
        assert p.caseStatus == "solved"
    warned = [w for w in _warn_lines(buf) if "withheld" in w]
    assert len(warned) == 2
    for w in warned:
        assert "Jamie" in w
        assert "2026-2027" in w


def test_jack_jill_2028_is_unchanged_with_a_stop_before_her_claim():
    """A stop before the claim month leaves the year alone. Jill claims in Feb 2028
    and works January only (`months worked` 1, not 0 — that means 'not given'): every
    month of her entitlement is a non-service month of the grace year, so nothing is
    withheld and the year is the no-test one."""
    p = _load("jack+jill")
    p.etMonths_in[1, _n(p, 2028)] = 1.0
    _solve(p, test_on=True)
    # The no-test year is 10 checks (entitlement Feb-Dec 2028, paid one month in arrears).
    assert p.zeta_in[1, _n(p, 2028)] == pytest.approx(10.0 * 1642.0 * _factor(59))
    assert np.all(p.ss_withheld_in[1] == 0)
    assert p.ss_arf_months_i[1] == 0


def test_spousal_record_is_credited_separately():
    """RS 00615.482 B.3, NOTE: ARFs are granted separately on each record. Jack claims at
    62y1m (Feb 2025) and earns $100k in 2026-2028, so his excess is charged to the family
    on his record: his own benefit, and Jill's spousal add-on (0.5 x 2,360 - 800) from its
    start at her claim in Feb 2028. Jill does not work here, so her own benefit — another
    record — is never charged."""
    p = _load("jack+jill")
    p.omega_in[1, :] = 0.0  # Jill does not work
    p.setSocialSecurity([2360, 800], [62.08333, 62.08333])
    _solve(p, test_on=True)
    assert p.ss_arf_months_i[0] == 36  # Jack: 2026-2028, twelve months each
    assert p.ss_arf_months_spousal_i[1] == 11  # the add-on, Feb-Dec 2028
    assert p.ss_arf_months_i[1] == 0  # Jill's own record is not charged
    assert np.all(p.zeta_in[1, _n(p, 2028) :] > 0)  # her own benefit is paid from her claim
    assert p.ss_withheld_in[1, _n(p, 2028)] > 0  # but her add-on is withheld there
    dic = build_summary_dic(p)
    assert "spouse" in dic["ARF months"]


def test_withheld_amounts_are_nominal():
    """ss_withheld_in is nominal: today's dollars scaled by gamma_n, so it
    drops into the worksheets next to the nominal SS column. The plan total in today's $
    is 11 withheld months of Jill's benefit."""
    p = _solve(_load("jack+jill"), test_on=True)
    today = float(np.sum(p.ss_withheld_in[1] / p.gamma_n[: p.N_n]))
    nominal = float(np.sum(p.ss_withheld_in[1]))
    assert today == pytest.approx(11 * 1642.0 * _factor(59), abs=0.02)
    assert nominal > today  # the withheld months are in 2028-2029


def test_every_solve_warns_once():
    """Two solves, two warnings: the skip is per solve, not per plan."""
    p = _load("alex+jamie")
    buf = _warn_log(p)
    for _ in range(2):
        _solve(p, test_on=True)
    warned = [w for w in _warn_lines(buf) if "withheld" in w]
    assert len(warned) == 2


# --------------------------------------------------------------------------------------
# Local search
# --------------------------------------------------------------------------------------


def test_local_search_warns_once():
    """The local search's two nested solves (the seeding loop, the search itself) are one
    user-visible solve: one warning."""
    p = _load("alex+jamie")
    buf = _warn_log(p)
    p.solve(
        p.objective,
        dict(
            p.solverOptions or {},
            withSSTaxability="optimize",
            mipStrategy="local-search",
            localSearchTime=2,
            localSearchStepTime=1,
        ),
    )
    assert p.caseStatus == "solved"
    warned = [w for w in _warn_lines(buf) if "withheld" in w]
    assert len(warned) == 1
    assert "Jamie" in warned[0]


# --------------------------------------------------------------------------------------
# A rejected setSocialSecurity, the Summary rows over a shortened Summary, the
# withholding in plan_metrics and the JSON outputs, the FRA month
# --------------------------------------------------------------------------------------


def _ss_state(p):
    return (
        np.array(p.ssecAmounts).copy(),
        np.array(p.ssecAges).copy(),
        p.ssecTrimPct,
        p.ssecTrimYear,
        p.ssecSurvivorClaimAge,
        p.zeta_in.copy(),
    )


def test_rejected_set_social_security_leaves_the_plan_unchanged():
    """A call that raises changes nothing (the behaviour before step 3, `d1d1681`): the
    PIAs, ages, trim and survivor settings and the streams stay those of the last call
    that succeeded, and the plan still solves. 71 is outside 62-70, refused by the
    reduction factor while the streams are built."""
    p = _load("jack+jill")
    before = _ss_state(p)
    with pytest.raises(ValueError, match="71"):
        p.setSocialSecurity([1000, 1000], [71, 71], trim_pct=10, trim_year=2040, survivor_claim_age="FRA")
    after = _ss_state(p)
    assert np.array_equal(after[0], before[0])
    assert np.array_equal(after[1], before[1])
    assert after[2:5] == before[2:5]
    assert np.array_equal(after[5], before[5])
    _solve(p)


def test_arf_months_row_follows_the_summary_window():
    """The ARF is granted at FRA. Jill (born 1966-01-15, FRA 67) reaches FRA in January
    2033: a Summary over 2026-2032 holds her 2028 withholding but not yet the ARF; one
    through 2033 holds both."""
    p = _solve(_load("jack+jill"), test_on=True)
    assert p.tobs[1] > 2 and p.yobs[1] == 1966 and p.mobs[1] == 1  # FRA month Jan 2033
    through_2032 = build_summary_dic(p, 2032 - THISYEAR + 1)
    assert through_2032["SS withheld by the earnings test (nominal)"] != "$0"
    assert through_2032["ARF months"] == "none"
    through_2033 = build_summary_dic(p, 2033 - THISYEAR + 1)
    assert through_2033["ARF months"] == "Jill 11 own"


def test_plan_metrics_report_the_withholding():
    """`owlcli compare` and the UI comparison read plan_metrics: the withholding is a key
    there (0 without the test), mapped to its Summary rows. Today's $: 11 withheld
    months of Jill's benefit (hand number, as above)."""
    from owlplanner.export import METRICS_COLUMN_MAP, plan_metrics

    on = _solve(_load("jack+jill"), test_on=True)
    m = plan_metrics(on)
    assert m["ss_withheld_today"] == pytest.approx(11 * 1642.0 * _factor(59), abs=0.02)
    assert m["ss_withheld_nominal"] == pytest.approx(float(np.sum(on.ss_withheld_in)))
    columns = on.summaryDf().columns
    for key in ("ss_withheld_today", "ss_withheld_nominal"):
        assert METRICS_COLUMN_MAP[key][0] in columns

    off = plan_metrics(_solve(_load("jack+jill"), test_on=False))
    assert off["ss_withheld_today"] == 0.0
    assert off["ss_withheld_nominal"] == 0.0


@pytest.mark.parametrize("day, fra_month", [(1, (2032, 11)), (2, (2033, 0)), (3, (2033, 0))])
def test_fra_month_matches_the_test_for_births_on_the_first_days(day, fra_month):
    """Only a birth on the 1st attains an age a month early (RS 00615.015,
    ``socsec._fra_conventional_age``); a birth on the 2nd attains it on the 1st of the birthday
    month. The plan's FRA month (Summary *ARF months*, the pays-nothing warning) must be the one
    the earnings test charges up to. Born January 1966, FRA 67 (born on the 1st: the 1965 rule,
    also 67)."""
    p = owl.Plan(["Al"], [f"1966-01-{day:02d}"], [90], "fra", verbose=False)
    fra = ss.getFRAs(p.yobs, p.mobs, p.tobs)[0]
    expected = ss._ent_start_abs(1966, 1, ss._fra_conventional_age(fra, day == 1))
    assert divmod(expected, 12) == fra_month
    assert p._ssFRAStartAbs()[0] == expected


def test_json_output_reports_the_withholding():
    """`owlcli run --output-format json` and the MCP's run_case serialize through
    `plan_to_dict`, whose summary keys are listed by hand: the withholding must be among
    them."""
    from owlplanner.cli.formatters import plan_to_dict

    p = _solve(_load("jack+jill"), test_on=True)
    s = plan_to_dict(p)["summary"]
    assert s["ss_withheld_nominal"] == round(float(np.sum(p.ss_withheld_in)))
    assert s["ss_withheld_nominal"] > 0  # Jill's 2028
    assert s["ss_withheld_today_dollars"] == round(float(np.sum(p.ss_withheld_in / p.gamma_n[: p.N_n])))


def _withheld_for_2027(monkeypatch, start, inflation):
    """Nominal amount withheld for \\$40,000 of 2027 wages by a plan starting in ``start``. The
    excess is below the year's benefit, so the PIA's dollar base does not enter."""

    class Day(datetime.date):
        @classmethod
        def today(cls):
            return datetime.date(start, 1, 1)

    with monkeypatch.context() as mp:
        for name, mod in list(sys.modules.items()):
            d = getattr(mod, "date", None) if name.startswith("owlplanner") and mod else None
            if isinstance(d, type) and issubclass(d, datetime.date):
                mp.setattr(mod, "date", Day)
        p = owl.Plan(["W"], ["1963-08-15"], [89], "t", verbose=False, logstreams=[io.StringIO()])
        p.setSocialSecurity([2000], [62 + 1 / 12])  # entitled before either plan
        p.omega_in[0, 2027 - start] = 40_000
        gamma = (1 + inflation) ** np.arange(p.N_n + 1)
        res = p._earningsTestResult(gamma_n=gamma)
    return float(np.sum(res.withheld_in[0] * gamma[: p.N_n]))


@pytest.mark.parametrize("inflation", [0.0, 0.025])
def test_withholding_in_a_published_year_does_not_depend_on_the_start_year(monkeypatch, inflation):
    """#231: a year's withholding depends only on its nominal earnings and its published nominal
    exempt amount, so a plan starting in 2026 and one starting in 2027 withhold the same for 2027
    (test contributed on the issue)."""
    early = _withheld_for_2027(monkeypatch, 2026, inflation)
    late = _withheld_for_2027(monkeypatch, 2027, inflation)
    assert late == pytest.approx((40_000 - 25_560) / 2, abs=1.0)
    assert early == pytest.approx(late, abs=1.0)
