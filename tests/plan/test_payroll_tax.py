"""
Tests for the employee payroll tax on earnings.

Every solve charges the employee's payroll tax on each person's earnings as a constant of
that year's cash-flow row (no option, no LP column, row or binary):

- social security tax, 6.2% of earnings up to the wage base (\\$184,500 in 2026, held at
  that level in today's dollars afterwards);
- Medicare tax, 1.45% of all earnings;
- Additional Medicare Tax, 0.9% of the household's combined earnings above \\$250,000
  through the year of the first death and \\$200,000 after (not indexed).

Earnings are the ones the SSA earnings test derives (``Plan._earnings_test_inputs``): in a
year with wages, ``anticipated wages`` plus that year's tax-deferred contributions.

Expected values are hand numbers from the primary text, not from the code under test:
IRS Pub. 15 (2026), "What's New" (rates and the \\$184,500 wage base), and the Instructions
for Form 8959, "Threshold Amounts for Additional Medicare Tax" (MFJ \\$250,000; single and
qualifying surviving spouse \\$200,000; "aren't indexed for inflation").

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

import glob
import io
import os

import numpy as np
import pytest

import owlplanner as owl
from owlplanner import tax_federal as tx
from owlplanner.export import METRICS_COLUMN_MAP, build_summary_dic, plan_metrics, plan_to_csv
from owlplanner.mylogging import Logger

_EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples")

# The examples with wages; the twelve others have no earnings, so no payroll tax.
WITH_WAGES = ["alex+jamie", "chris+pat", "jack+jill", "joe", "john+sally", "jon+jane", "riley+casey"]

# jack+jill (HFP, nominal): Jack earns $100,000 in 2026-2028 and defers $15,000 to his 401k in
# 2026-2027; Jill earns $80,000 in 2026-2027 and $85,000 in 2028. Earnings are wages plus the
# deferrals: $195,000 in 2026-2027, $185,000 in 2028, all under the base, the household under
# $250,000, so 7.65% of them.
JJ_PAYROLL = {2026: 0.0765 * 195_000.0, 2027: 0.0765 * 195_000.0, 2028: 0.0765 * 185_000.0}


def _load(case):
    return owl.readConfig(os.path.join(_EXAMPLES, "Case_" + case + ".toml"), verbose=False,
                          logstreams=[io.StringIO()])


def _solve(p):
    p.solve(p.objective, dict(p.solverOptions or {}))
    assert p.caseStatus == "solved"
    return p


def _n(p, year):
    return int(year) - int(p.year_n[0])


# --------------------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------------------


def test_single_filer_wage_base_cap():
    """Year 0: \\$85,000, under the base. Year 1, after 10% inflation: \\$250,000 nominal, above
    the base of \\$184,500 x 1.1 = \\$202,950; Medicare on all of it, and 0.9% of the \\$50,000
    above the single threshold, which is not indexed. Year 2: no earnings."""
    earnings = np.array([[85_000.0, 250_000.0, 0.0]])
    payroll = tx.payrollTax(1, earnings, np.array([1.0, 1.1, 1.21, 1.331]), n_d=3, N_n=3)
    assert payroll == pytest.approx([
        0.0765 * 85_000.0,
        0.062 * 202_950.0 + 0.0145 * 250_000.0 + 0.009 * 50_000.0,
        0.0,
    ])


def test_couple_threshold_switches_at_first_death():
    """Year 0, joint: \\$200,000 + \\$100,000. Social security tax is per person (the first
    capped at the base); the 0.9% is on the combined \\$300,000 above \\$250,000. From year 1
    (n_d = 1) the survivor files single: \\$230,000, 0.9% above \\$200,000."""
    earnings = np.array([[200_000.0, 0.0], [100_000.0, 230_000.0]])
    payroll = tx.payrollTax(2, earnings, np.ones(3), n_d=1, N_n=2)
    assert payroll == pytest.approx([
        0.062 * 184_500.0 + 0.0145 * 200_000.0 + 0.0765 * 100_000.0 + 0.009 * 50_000.0,
        0.062 * 184_500.0 + 0.0145 * 230_000.0 + 0.009 * 30_000.0,
    ])


def test_two_earners_each_under_200k():
    """Form 8959: the joint threshold is on the combined Medicare wages, so two \\$150,000
    earners owe 0.9% of \\$50,000 although neither is above \\$200,000."""
    earnings = np.array([[150_000.0], [150_000.0]])
    payroll = tx.payrollTax(2, earnings, np.ones(2), n_d=1, N_n=1)
    assert payroll == pytest.approx([0.0765 * 300_000.0 + 0.009 * 50_000.0])


def test_couple_with_no_first_death_in_the_plan():
    """n_d = N_n (no death in the plan): joint throughout."""
    earnings = np.array([[130_000.0, 130_000.0], [100_000.0, 100_000.0]])
    payroll = tx.payrollTax(2, earnings, np.ones(3), n_d=2, N_n=2)
    assert payroll == pytest.approx([0.0765 * 230_000.0] * 2)


# --------------------------------------------------------------------------------------
# On the plan
# --------------------------------------------------------------------------------------


def test_jack_jill_by_hand():
    p = _solve(_load("jack+jill"))
    for year, amount in JJ_PAYROLL.items():
        assert p.payroll_n[_n(p, year)] == pytest.approx(amount)
    assert np.all(p.payroll_n[_n(p, 2029):] == 0)


def test_refreshed_at_solve_time():
    """Built from the earnings the plan holds at each solve, not at HFP read."""
    p = _solve(_load("jack+jill"))
    p.omega_in[1, _n(p, 2026)] = 90_000.0
    _solve(p)
    assert p.payroll_n[_n(p, 2026)] == pytest.approx(0.0765 * 205_000.0)


def test_cash_flow_balances_on_a_case_with_wages():
    """The tax is paid from the plan: the cash-flow identity holds with it on the outflow side,
    and _check_cashflow_balance does not warn."""
    p = _load("jack+jill")
    buf = io.StringIO()
    p.mylog = Logger(verbose=False, logstreams=[buf])
    _solve(p)
    assert "Cash flow balance off" not in buf.getvalue()
    lhs = (
        p.g_n + p.s_n + p.T_n + p.U_n + p.J_n + p.st_T_n + p.m_n + p.M_n + p.aca_costs_n
        + p.debt_payments_n + p.payroll_n
    )
    rhs = (
        np.sum(p.omega_in + p.other_inc_in + p.netinv_in + p.zetaBar_in + p.piBar_in + p.spiaBar_in, axis=0)
        + np.sum(p.Lambda_in, axis=0)
        + p.fixed_assets_ordinary_income_n
        + p.fixed_assets_capital_gains_n
        + p.fixed_assets_tax_free_n
        + np.sum(p.w_ijn, axis=(0, 1))
    )
    np.testing.assert_allclose(lhs, rhs, atol=1.0)


def test_cash_flow_sheet_has_the_column_and_balances():
    """The Cash Flow sheet's columns, the payroll tax among them, sum to net spending."""
    p = _solve(_load("jack+jill"))
    ws = p.saveWorkbook(saveToFile=False)["Cash Flow"]
    rows = list(ws.iter_rows(values_only=True))
    headers = list(rows[0])
    assert headers.index("payroll tax") == headers.index("NIIT") + 1
    col = headers.index("payroll tax")
    spend = headers.index("net spending")
    others = [k for k, h in enumerate(headers) if h not in ("year", "net spending")]
    for row in rows[1:]:
        assert sum(row[k] for k in others) == pytest.approx(row[spend], abs=1.0)
    assert rows[1 + _n(p, 2026)][col] < 0
    assert rows[1 + _n(p, 2029)][col] == 0


def test_not_in_the_income_tax():
    """T_n is still the bracket sum, and the effective tax rate still an income-tax rate."""
    p = _solve(_load("jack+jill"))
    assert p.T_n == pytest.approx(np.sum(p.T_tn, axis=0))
    rate = np.sum(p.T_n + p.U_n + p.J_n) / np.sum(p.G_n + p.Q_n)
    assert p._actual_effective_tax_rate() == pytest.approx(rate)


def test_outputs_report_it(tmp_path, monkeypatch):
    p = _solve(_load("jack+jill"))
    total = sum(JJ_PAYROLL.values())
    inv_g = 1.0 / p.gamma_n[: p.N_n]

    m = plan_metrics(p)
    assert m["payroll_tax_nominal"] == pytest.approx(total)
    assert m["payroll_tax_today"] == pytest.approx(float(np.sum(p.payroll_n * inv_g)))
    columns = p.summaryDf().columns
    for key in ("payroll_tax_today", "payroll_tax_nominal"):
        assert METRICS_COLUMN_MAP[key][0] in columns

    taxes = float(np.sum((p.T_n + p.U_n + p.J_n + p.payroll_n) * inv_g))
    assert p.lifetime_allocation()["outflows"]["taxes"] == pytest.approx(taxes)

    bills = p.T_n + p.U_n + p.medicare_n + p.J_n + p.aca_costs_n + p.st_T_n + p.payroll_n
    income = p.saveWorkbook(saveToFile=False)["Income"]
    head = [c.value for c in income[1]]
    col = head.index("Tax bills + Med.")
    n = _n(p, 2026)
    assert income.cell(row=2 + n, column=col + 1).value == pytest.approx(bills[n] * inv_g[n])

    monkeypatch.chdir(tmp_path)
    plan_to_csv(p, "jj", p.mylog)
    import pandas as pd

    df = pd.read_csv(glob.glob(str(tmp_path / "*.csv"))[0])
    assert df["payroll tax"][n] == pytest.approx(-JJ_PAYROLL[2026])
    assert df["Tax bills + Med."][n] == pytest.approx(bills[n])


def test_summary_line_for_every_case():
    """Present, at \\$0, for a case without earnings, so plans compare row for row; no Cash Flow
    or CSV column then."""
    p = _solve(_load("jack+jill"))
    dic = build_summary_dic(p)
    nominal = float(dic["Total payroll tax paid (nominal)"].lstrip("$").replace(",", ""))
    assert nominal == pytest.approx(sum(JJ_PAYROLL.values()), abs=1.0)

    q = _load("jack+jill")
    q.omega_in[:, :] = 0.0
    _solve(q)
    assert np.all(q.payroll_n == 0)
    dic = build_summary_dic(q)
    assert dic["Total payroll tax paid (nominal)"] == "$0"
    assert plan_metrics(q)["payroll_tax_nominal"] == 0.0
    ws = q.saveWorkbook(saveToFile=False)["Cash Flow"]
    assert "payroll tax" not in [c.value for c in ws[1]]


def _no_earnings_examples():
    cases = sorted(os.path.basename(f)[len("Case_"):-len(".toml")]
                   for f in glob.glob(os.path.join(_EXAMPLES, "Case_*.toml")))
    cases = [c for c in cases if c not in WITH_WAGES]
    assert len(cases) == 12  # an empty glob would make the test below check nothing
    return cases


@pytest.mark.parametrize("case", _no_earnings_examples())
def test_no_earnings_no_tax(case):
    """The twelve examples without wages pay nothing, so their LP is unchanged."""
    p = _load(case)
    earnings, _ = p._earnings_test_inputs()
    assert not np.any(earnings > 0)
    assert np.all(tx.payrollTax(p.N_i, earnings, np.ones(p.N_n + 1), p.n_d, p.N_n) == 0)


@pytest.mark.parametrize("case", WITH_WAGES)
def test_every_example_with_wages_pays_it(case):
    p = _load(case)
    earnings, _ = p._earnings_test_inputs()
    assert np.any(earnings > 0)
    assert np.sum(tx.payrollTax(p.N_i, earnings, np.ones(p.N_n + 1), p.n_d, p.N_n)) > 0
