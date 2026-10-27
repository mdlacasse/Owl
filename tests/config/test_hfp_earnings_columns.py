"""
Tests for the HFP input of the SSA earnings test, ``months worked``, and for the earnings the
test derives from the other columns (round trip, defaults, refusals), following the
optional-column conventions of ``hfp_io.py``.

Month / money conventions:
  earnings             not a column: ``anticipated wages`` plus that year's tax-deferred
                       contributions (wages are the wages in AGI, net of them, #221), in a
                       year with wages; nominal $.
  ``months worked``    0-12, months of work at the start of the year. Absent or 0 →
                       12 when that year's earnings are positive, else 0.

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
import tempfile
from datetime import date

import pytest

import owlplanner as owl
from owlplanner import hfp_io

thisyear = date.today().year


def _plan(name="Alice", birth="1970-01-15", remaining=30):
    birth_year = int(birth[:4])
    expectancy = (thisyear - birth_year) + remaining
    return owl.Plan([name], [birth], [expectancy], "Step 2", verbose=False)


def _write_and_reload(p, name="Alice", birth="1970-01-15", remaining=30, drop=None):
    """Save the plan's HFP table to a temp xlsx (optionally dropping columns) and reload."""
    df = p.timeLists[name].copy()
    if drop:
        df = df.drop(columns=drop)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        df.to_excel(tmp.name, sheet_name=name, index=False)
        p2 = _plan(name=name, birth=birth, remaining=remaining)
        p2.readHFP(tmp.name)
        return p2, tmp.name
    except Exception:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise


# --------------------------------------------------------------------------------------
# Schema surface
# --------------------------------------------------------------------------------------


def test_months_worked_is_a_recognized_header():
    """One optional per-person column in the Wages and Contributions table; earnings are
    derived, not entered."""
    cols = hfp_io.timeHorizonItems()
    assert "months worked" in cols
    assert "gross earnings" not in cols
    assert cols.index("months worked") > cols.index("year")


def test_typo_near_months_worked_is_still_rejected():
    """A header that folds to a recognized one is a typo, not a helper column."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"].rename(columns={"months worked": "Months-Worked"})
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        df.to_excel(tmp.name, sheet_name="Alice", index=False)
        p2 = _plan()
        with pytest.raises(Exception, match="typo|Months|months"):
            p2.readHFP(tmp.name)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


# --------------------------------------------------------------------------------------
# Load into plan arrays; the derived earnings
# --------------------------------------------------------------------------------------


def test_months_worked_lands_in_its_array():
    """``setContributions`` maps the column to ``etMonths_in``."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    # Plan-year 0 is row 5 (five lead-in years).
    df.loc[df.index[5], "months worked"] = 6
    df.loc[df.index[6], "months worked"] = 12
    p.setContributions()
    assert p.etMonths_in.shape == (p.N_i, p.N_n)
    assert list(p.etMonths_in[0, :3]) == [6, 12, 0]


def test_earnings_add_back_the_pre_tax_contributions_wages_are_net_of():
    """``anticipated wages`` are the wages in AGI, net of pre-tax contributions (#221), while
    the test counts wages before them (W-2 box 5): the earnings add back the year's 401k and
    IRA contributions. After-tax ones (taxable, Roth 401k, Roth IRA) stay in the wages, and a
    payroll HSA is not in box 5. Contributions in a year without wages are not earnings."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 60_000.0
    for col, amount in (("taxable ctrb", 1_000.0), ("401k ctrb", 2_000.0), ("Roth 401k ctrb", 3_000.0),
                        ("IRA ctrb", 4_000.0), ("Roth IRA ctrb", 5_000.0), ("HSA ctrb", 6_000.0)):
        df.loc[df.index[5], col] = amount
    df.loc[df.index[6], "IRA ctrb"] = 7_000.0  # no wages that year
    p.setContributions()
    earnings, months = p._earnings_test_inputs()
    assert earnings[0, 0] == pytest.approx(60_000.0 + 2_000.0 + 4_000.0)
    assert earnings[0, 1] == 0.0
    assert list(months[0, :2]) == [12, 0]


def test_pay_all_deferred_to_the_401k_is_earnings():
    """A 401k elective deferral is wages for FICA and the earnings test even when it took all
    of the year's pay (#229): no step at the first dollar of ``anticipated wages``. An IRA
    contribution rides along in a year with pay, the 401k's included."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "401k ctrb"] = 23_500.0
    df.loc[df.index[6], "anticipated wages"] = 1.0
    df.loc[df.index[6], "401k ctrb"] = 23_500.0
    df.loc[df.index[7], "401k ctrb"] = 23_500.0
    df.loc[df.index[7], "IRA ctrb"] = 7_000.0
    p.setContributions()
    earnings, months = p._earnings_test_inputs()
    assert earnings[0, 0] == pytest.approx(23_500.0)
    assert earnings[0, 1] == pytest.approx(23_501.0)
    assert earnings[0, 2] == pytest.approx(30_500.0)
    assert list(months[0, :3]) == [12, 12, 12]


def test_employer_contributions_are_not_earnings():
    """An employer contribution is deposited in the tax-deferred account but was never wages
    (26 U.S.C. 3121(a)(5)(A)): it is not earnings, with or without pay, and does not make a year
    without pay look like one with it, so an IRA contribution beside it stays out too. The
    workbook keeps it in its own column."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 60_000.0
    df.loc[df.index[5], "401k ctrb"] = 10_000.0
    df.loc[df.index[5], "employer ctrb"] = 3_000.0
    df.loc[df.index[6], "employer ctrb"] = 5_000.0
    df.loc[df.index[6], "IRA ctrb"] = 7_000.0
    df.loc[df.index[4], "employer ctrb"] = 2_000.0  # lead-in year
    p.setContributions()
    assert p.kappa_ijn[0, 1, 0] == pytest.approx(13_000.0)
    assert p.kappa_ijn[0, 1, 1] == pytest.approx(12_000.0)
    earnings, months = p._earnings_test_inputs()
    assert earnings[0, 0] == pytest.approx(70_000.0)
    assert earnings[0, 1] == 0.0 and months[0, 1] == 0

    rebuilt, _ = hfp_io.build_hfp_dataframes(p)
    assert hfp_io.time_lists_agree(p.timeLists, rebuilt)
    out = rebuilt["Alice"]
    assert list(out["employer ctrb"].iloc[4:7]) == pytest.approx([2_000.0, 3_000.0, 5_000.0])
    assert list(out["IRA ctrb"].iloc[4:7]) == pytest.approx([0.0, 0.0, 7_000.0])
    assert list(out["401k ctrb"].iloc[4:7]) == pytest.approx([0.0, 10_000.0, 0.0])


def test_absent_months_worked_defaults_by_earnings():
    """``months worked`` absent (or 0) → 12 in a year with earnings, else 0. The column is
    recorded as absent and read as zero like any other."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 90_000.0
    df.loc[df.index[6], "anticipated wages"] = 50_000.0
    p.setContributions()

    p2, tmp = _write_and_reload(p, drop=["months worked"])
    try:
        assert "months worked" in p2.hfpAbsentCols["Alice"]
        earnings, months = p2._earnings_test_inputs()
        assert earnings[0, 0] == pytest.approx(90_000.0)
        assert earnings[0, 1] == pytest.approx(50_000.0)
        assert list(months[0, :3]) == [12, 12, 0]
    finally:
        os.unlink(tmp)


def test_zero_months_worked_means_the_default():
    """A ``months worked`` of 0 in a year with earnings means "not given" (12), not "no
    work": earnings with no month of work would be ignored by the test
    (``countable_earnings`` counts nothing over zero months)."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 90_000.0
    df.loc[df.index[5], "months worked"] = 0
    df.loc[df.index[6], "anticipated wages"] = 40_000.0
    df.loc[df.index[6], "months worked"] = 5
    p.setContributions()
    assert p.etMonths_in[0, 0] == 0  # the column as entered
    _, months = p._earnings_test_inputs()
    assert months[0, 0] == 12
    assert months[0, 1] == 5  # a positive entry is used as is


def test_case_without_workbook_feeds_the_test_from_wages():
    """A UI case with no workbook starts from ``zeroWagesAndContributions`` (every column
    at 0) and the user types wages; the UI then re-reads its tables
    (``owlbridge._setContributions``). The MCP assistant writes ``omega_in`` and
    ``kappa_ijn`` directly. Both must reach the earnings test."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5:8], "anticipated wages"] = 80_000.0
    p.readHFP({"Alice": df.copy()}, houseTables=False)
    earnings, months = p._earnings_test_inputs()
    assert earnings[0, :3] == pytest.approx([80_000.0] * 3)
    assert list(months[0, :4]) == [12, 12, 12, 0]

    q = _plan()
    q.zeroWagesAndContributions()
    q.omega_in[0, :2] = 70_000.0  # assistant/tools.py writes wages this way
    q.kappa_ijn[0, 1, 0] = 10_000.0  # and contributions this way
    q.kappa_ijn[0, 3, 1] = 4_000.0  # HSA: not box 5
    earnings, months = q._earnings_test_inputs()
    assert earnings[0, :2] == pytest.approx([80_000.0, 70_000.0])
    assert list(months[0, :3]) == [12, 12, 0]


# --------------------------------------------------------------------------------------
# Round trip
# --------------------------------------------------------------------------------------


def test_round_trip_workbook_plan_workbook():
    """Workbook → plan → workbook keeps the column (values, not just the header)."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 50_000.0
    df.loc[df.index[5], "months worked"] = 7
    p.setContributions()

    p2, tmp = _write_and_reload(p)
    try:
        assert p2.etMonths_in[0, 0] == 7
        wb = p2.saveContributions()
        sheet = wb["Alice"]
        headers = [c.value for c in sheet[1]]
        assert "gross earnings" not in headers
        i_months = headers.index("months worked") + 1
        # Row 1 is the header; plan year 0 is Excel row 7 (five lead-in rows + header).
        assert sheet.cell(row=7, column=i_months).value == 7
    finally:
        os.unlink(tmp)


def test_clone_with_new_expectancy_keeps_the_column():
    """``clone`` with a new horizon keeps ``months worked``.

    ``clone`` re-applies HFP from ``rawHFP``, so the plan must have been through
    ``readHFP`` (the same way the UI syncs the per-person tables). Account balances
    are required because clone serializes the full plan.
    """
    p = _plan(remaining=30)
    p.setAccountBalances(taxable=[100], taxDeferred=[500], taxFree=[100])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [60, 40, 0, 0]]])
    p.setRates("conservative")
    p.setSpendingProfile("flat")
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 77_000.0
    df.loc[df.index[5], "months worked"] = 4
    df.loc[df.index[6], "months worked"] = 12
    p.setContributions()
    # Populate rawHFP the way the UI sync does, so clone can rebuild from it.
    p.readHFP({n: p.timeLists[n] for n in p.inames}, houseTables=False)

    c = owl.clone(p, expectancy=[(thisyear - 1970) + 25], verbose=False)
    assert c.etMonths_in[0, 0] == 4
    assert c.etMonths_in[0, 1] == 12
    assert c._earnings_test_inputs()[0][0, 0] == pytest.approx(77_000.0)


# --------------------------------------------------------------------------------------
# Refusals and resets
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad_months", [-1, 13, 12.5, 6.5])
def test_months_worked_outside_0_12_refused(bad_months):
    """Bad values refused like other columns. Months must be an integer in [0, 12].

    12.5 is outside [0, 12] on the reals; 6.5 is inside the interval but is not a whole
    month. ``months worked`` is a count (``earnings_test`` takes ``int``).
    """
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"].copy()
    # The live table may hold an integer dtype; allow a bad entry into the sheet itself.
    df["months worked"] = df["months worked"].astype(float)
    df.loc[df.index[5], "months worked"] = bad_months
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        df.to_excel(tmp.name, sheet_name="Alice", index=False)
        p2 = _plan()
        with pytest.raises(Exception, match="months worked"):
            p2.readHFP(tmp.name)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


def test_zero_wages_reset_clears_the_column():
    """``zeroWagesAndContributions`` rebuilds the tables with the column present."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "months worked"] = 3
    p.setContributions()
    p.zeroWagesAndContributions()
    p.setContributions()
    assert (p.etMonths_in == 0).all()
    assert "months worked" in p.timeLists["Alice"].columns
    assert p.hfpAbsentCols["Alice"] == []


def test_fresh_plan_has_a_zero_months_array():
    """A new Plan starts with no months worked (like omega_in)."""
    p = _plan()
    assert (p.etMonths_in == 0).all()
    assert p.etMonths_in.shape == (p.N_i, p.N_n)


# --------------------------------------------------------------------------------------
# UI sync, notices, example workbooks
# --------------------------------------------------------------------------------------


class _Log:
    """Collects log lines; stands in for ``Plan.mylog``."""

    def __init__(self):
        self.lines = []

    def print(self, msg, tag=None):
        self.lines.append(f"{tag}: {msg}")

    def vprint(self, msg, tag=None):
        self.lines.append(f"{tag}: {msg}")


def _sheet_without_months(edit, name="Alice", birth="1970-01-15"):
    """Write a one-sheet workbook without ``months worked``; ``edit(df)`` fills it first."""
    p = _plan(name=name, birth=birth)
    p.zeroWagesAndContributions()
    df = p.timeLists[name].copy()
    edit(df)
    df = df.drop(columns=["months worked"])
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    df.to_excel(tmp.name, sheet_name=name, index=False)
    return tmp.name


def _load(path, name="Alice", birth="1970-01-15"):
    p = _plan(name=name, birth=birth)
    p.mylog = _Log()
    p.readHFP(path)
    return p


def test_ui_sync_follows_wage_edits():
    """The UI re-reads its edited tables (``owlbridge._setContributions``
    → ``readHFP({iname: table})``), which carry every column. The earnings test must see
    the wages after the sync, and wages edited afterwards (no frozen copy)."""

    def edit(df):
        df.loc[df.index[5:8], "anticipated wages"] = 80_000.0

    path = _sheet_without_months(edit)
    try:
        p = _load(path)
        tables = {n: p.timeLists[n].copy() for n in p.inames}
        p.readHFP(tables, houseTables=False)
        earnings, months = p._earnings_test_inputs()
        assert earnings[0, :3] == pytest.approx([80_000.0] * 3)
        assert list(months[0, :4]) == [12, 12, 12, 0]

        tables["Alice"].loc[tables["Alice"].index[5], "anticipated wages"] = 60_000.0
        p.readHFP(tables, houseTables=False)
        earnings, _ = p._earnings_test_inputs()
        assert earnings[0, 0] == pytest.approx(60_000.0)
    finally:
        os.unlink(path)


def test_absent_months_worked_is_not_reported_as_zero():
    """The column read as zero means "12 months in a year with wages", so the "treated
    as zero" notice must not list it (it still lists the others)."""

    def edit(df):
        df.loc[df.index[5], "anticipated wages"] = 80_000.0

    path = _sheet_without_months(edit)
    try:
        p = _load(path)
        zero_lines = [line for line in p.mylog.lines if "treated as zero" in line]
        assert not any("months worked" in line for line in zero_lines)
    finally:
        os.unlink(path)


def test_blank_months_worked_cell_reads_as_zero():
    """A blank cell reads as zero like in every other column (Documentation: "leave it
    blank where it does not apply"). Zero means the default: 12 in a year with earnings."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"].copy()
    df["months worked"] = df["months worked"].astype(float)
    df.loc[df.index[5], "anticipated wages"] = 50_000.0
    df.loc[df.index[5], "months worked"] = 6
    df.loc[df.index[6], "anticipated wages"] = 30_000.0
    df.loc[df.index[6], "months worked"] = float("nan")
    df.loc[df.index[7], "months worked"] = float("nan")
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        df.to_excel(tmp.name, sheet_name="Alice", index=False)
        p2 = _load(tmp.name)
        assert list(p2.etMonths_in[0, :3]) == [6, 0, 0]
        _, months = p2._earnings_test_inputs()
        assert list(months[0, :3]) == [6, 12, 0]
    finally:
        os.unlink(tmp.name)


@pytest.mark.toml
def test_example_workbooks_feed_the_test_from_wages():
    """The example workbooks do not carry ``months worked``, so the test reads a full year
    of the derived earnings: Jill (jack+jill) has $85,000 of wages and no contribution in
    2028, which the earnings test must see."""
    from pathlib import Path

    case = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"
    p = owl.readConfig(str(case), verbose=False)
    j = p.inames.index("Jill")
    n = 2028 - thisyear
    earnings, months = p._earnings_test_inputs()
    assert earnings[j, n] == pytest.approx(85_000.0)
    assert months[j, n] == 12
