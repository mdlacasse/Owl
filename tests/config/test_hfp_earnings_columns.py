"""
Tests for the HFP columns of the SSA earnings test: ``gross earnings`` and ``months worked``
(round trip, defaults, refusals, warnings), following the optional-column conventions of
``hfp_io.py``.

Month / money conventions:
  ``gross earnings``   nominal $, W-2 box 5 + net SE. Absent → ``anticipated wages``
                       plus a warning naming years where a contribution column is non-zero.
  ``months worked``    0-12, months of work at the start of the year. Absent →
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


def test_columns_are_recognized_hfp_headers():
    """Two optional per-person columns in the Wages and Contributions table."""
    cols = hfp_io.timeHorizonItems()
    assert "gross earnings" in cols
    assert "months worked" in cols
    # Only 'year' is required; these two are optional like the rest.
    assert "year" in cols
    assert cols.index("gross earnings") > cols.index("year")


def test_typo_near_new_names_is_still_rejected():
    """A header that folds to a recognized one is a typo, not a helper column."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"].rename(columns={"gross earnings": "gross earnings "})
    # The trailing-space variant folds to 'gross earnings' and must be refused, not dropped.
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        df.to_excel(tmp.name, sheet_name="Alice", index=False)
        p2 = _plan()
        with pytest.raises(Exception, match="typo|Gross|gross"):
            p2.readHFP(tmp.name)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


# --------------------------------------------------------------------------------------
# Load into plan arrays
# --------------------------------------------------------------------------------------


def test_present_columns_land_in_et_arrays():
    """``setContributions`` maps the two columns to ``etEarnings_in`` / ``etMonths_in``."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    # Plan-year 0 is row 5 (five lead-in years).
    df.loc[df.index[5], "gross earnings"] = 120_000.0
    df.loc[df.index[5], "months worked"] = 6
    df.loc[df.index[6], "gross earnings"] = 40_000.0
    df.loc[df.index[6], "months worked"] = 12
    p.setContributions()

    assert hasattr(p, "etEarnings_in")
    assert hasattr(p, "etMonths_in")
    assert p.etEarnings_in.shape == (p.N_i, p.N_n)
    assert p.etMonths_in.shape == (p.N_i, p.N_n)
    assert p.etEarnings_in[0, 0] == pytest.approx(120_000.0)
    assert p.etMonths_in[0, 0] == 6
    assert p.etEarnings_in[0, 1] == pytest.approx(40_000.0)
    assert p.etMonths_in[0, 1] == 12
    assert p.etEarnings_in[0, 2] == 0
    assert p.etMonths_in[0, 2] == 0


def test_absent_gross_earnings_falls_back_to_anticipated_wages():
    """Absent ``gross earnings`` → ``anticipated wages``. The column is still
    recorded as absent and read as zero like any other; zero means "not given", and the
    earnings test then uses the year's wages (``Plan._earnings_test_inputs``).
    The rule lives where the test's inputs are built, so it holds
    for workbooks, UI tables and the MCP alike, and follows later edits to wages."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 90_000.0
    df.loc[df.index[6], "anticipated wages"] = 50_000.0
    p.setContributions()

    p2, tmp = _write_and_reload(p, drop=["gross earnings"])
    try:
        assert "gross earnings" in p2.hfpAbsentCols["Alice"]
        assert p2.timeLists["Alice"]["gross earnings"].iloc[5] == 0
        assert p2.etEarnings_in[0, 0] == 0
        earnings, months = p2._earnings_test_inputs()
        assert earnings[0, 0] == pytest.approx(90_000.0)
        assert earnings[0, 1] == pytest.approx(50_000.0)
        assert list(months[0, :3]) == [12, 12, 0]
    finally:
        os.unlink(tmp)


def test_absent_months_worked_defaults_by_earnings():
    """``months worked`` absent (or 0) → 12 when that year's effective earnings are
    positive, else 0. Effective earnings are ``gross earnings`` when positive, else
    ``anticipated wages``."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "gross earnings"] = 95_000.0
    df.loc[df.index[6], "anticipated wages"] = 90_000.0  # gross 0: wages are used
    p.setContributions()

    p2, tmp = _write_and_reload(p, drop=["months worked"])
    try:
        assert "months worked" in p2.hfpAbsentCols["Alice"]
        earnings, months = p2._earnings_test_inputs()
        assert earnings[0, 0] == pytest.approx(95_000.0)
        assert earnings[0, 1] == pytest.approx(90_000.0)
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
    df.loc[df.index[5], "gross earnings"] = 90_000.0
    df.loc[df.index[5], "months worked"] = 0
    df.loc[df.index[6], "gross earnings"] = 40_000.0
    df.loc[df.index[6], "months worked"] = 5
    p.setContributions()
    assert p.etMonths_in[0, 0] == 0  # the column as entered
    _, months = p._earnings_test_inputs()
    assert months[0, 0] == 12
    assert months[0, 1] == 5  # a positive entry is used as is


def test_zero_gross_earnings_means_wages():
    """A ``gross earnings`` of 0 means "not given": the test uses ``anticipated wages``.
    A positive entry is used as is (it is meant to be the larger W-2 box 5 amount)."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 90_000.0
    df.loc[df.index[6], "anticipated wages"] = 90_000.0
    df.loc[df.index[6], "gross earnings"] = 101_000.0
    p.setContributions()
    earnings, _ = p._earnings_test_inputs()
    assert earnings[0, 0] == pytest.approx(90_000.0)
    assert earnings[0, 1] == pytest.approx(101_000.0)


def test_case_without_workbook_feeds_the_test_from_wages():
    """A UI case with no workbook starts from
    ``zeroWagesAndContributions`` (every column at 0) and the user types wages; the UI
    then re-reads its tables (``owlbridge._setContributions``). The MCP assistant writes
    ``omega_in`` directly. Both must reach the earnings test."""
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
    earnings, months = q._earnings_test_inputs()
    assert earnings[0, :2] == pytest.approx([70_000.0] * 2)
    assert list(months[0, :3]) == [12, 12, 0]


def test_fallback_warning_names_deferral_years():
    """A warning names the years where the test falls back to wages and a contribution
    column is non-zero (*taxable*, *401k*, *Roth 401k*, *IRA*, *Roth IRA ctrb*).

    The warning is not given at HFP read (it would be noise on most examples): each solve
    calls ``Plan._warnGrossEarningsFallback(entitled_from)``, with each person's first
    year of entitlement."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 90_000.0
    df.loc[df.index[5], "401k ctrb"] = 10_000.0
    df.loc[df.index[6], "anticipated wages"] = 50_000.0  # no deferral this year
    p.setContributions()
    warn = _fallback_warnings(p, [thisyear])
    assert len(warn) == 1
    assert str(thisyear) in warn[0]
    assert str(thisyear + 1) not in warn[0]


# --------------------------------------------------------------------------------------
# Round trip
# --------------------------------------------------------------------------------------


def test_round_trip_workbook_plan_workbook():
    """Workbook → plan → workbook keeps both columns (values, not just headers)."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "gross earnings"] = 111_000.0
    df.loc[df.index[5], "months worked"] = 7
    p.setContributions()

    p2, tmp = _write_and_reload(p)
    try:
        assert p2.etEarnings_in[0, 0] == pytest.approx(111_000.0)
        assert p2.etMonths_in[0, 0] == 7
        # Write-back carries the column *values*, not just the headers.
        wb = p2.saveContributions()
        sheet = wb["Alice"]
        headers = [c.value for c in sheet[1]]
        i_gross = headers.index("gross earnings") + 1
        i_months = headers.index("months worked") + 1
        # Row 1 is the header; plan year 0 is Excel row 7 (five lead-in rows + header).
        assert sheet.cell(row=7, column=i_gross).value == pytest.approx(111_000.0)
        assert sheet.cell(row=7, column=i_months).value == 7
    finally:
        os.unlink(tmp)


def test_clone_with_new_expectancy_keeps_columns():
    """``clone`` with a new horizon keeps the two columns.

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
    df.loc[df.index[5], "gross earnings"] = 77_000.0
    df.loc[df.index[5], "months worked"] = 4
    df.loc[df.index[6], "gross earnings"] = 88_000.0
    df.loc[df.index[6], "months worked"] = 12
    p.setContributions()
    # Populate rawHFP the way the UI sync does, so clone can rebuild from it.
    p.readHFP({n: p.timeLists[n] for n in p.inames}, houseTables=False)

    c = owl.clone(p, expectancy=[(thisyear - 1970) + 25], verbose=False)
    assert c.etEarnings_in[0, 0] == pytest.approx(77_000.0)
    assert c.etMonths_in[0, 0] == 4
    assert c.etEarnings_in[0, 1] == pytest.approx(88_000.0)
    assert c.etMonths_in[0, 1] == 12


# --------------------------------------------------------------------------------------
# Refusals
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


def test_negative_gross_earnings_refused():
    """Negative earnings refused (like other amounts)."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "gross earnings"] = -1.0
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        df.to_excel(tmp.name, sheet_name="Alice", index=False)
        p2 = _plan()
        with pytest.raises(Exception, match="gross earnings"):
            p2.readHFP(tmp.name)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


def test_zero_wages_reset_clears_et_arrays_and_columns():
    """``zeroWagesAndContributions`` rebuilds the tables with both columns present."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "gross earnings"] = 10_000.0
    df.loc[df.index[5], "months worked"] = 3
    p.setContributions()
    p.zeroWagesAndContributions()
    p.setContributions()
    assert (p.etEarnings_in == 0).all()
    assert (p.etMonths_in == 0).all()
    assert "gross earnings" in p.timeLists["Alice"].columns
    assert "months worked" in p.timeLists["Alice"].columns
    assert p.hfpAbsentCols["Alice"] == []


def test_fresh_plan_has_zero_et_arrays():
    """A new Plan starts with zero earnings-test inputs (like omega_in)."""
    p = _plan()
    assert (p.etEarnings_in == 0).all()
    assert (p.etMonths_in == 0).all()
    assert p.etEarnings_in.shape == (p.N_i, p.N_n)
    assert p.etMonths_in.shape == (p.N_i, p.N_n)


# --------------------------------------------------------------------------------------
# UI sync, warnings, example workbooks
# --------------------------------------------------------------------------------------


class _Log:
    """Collects log lines; stands in for ``Plan.mylog``."""

    def __init__(self):
        self.lines = []

    def print(self, msg, tag=None):
        self.lines.append(f"{tag}: {msg}")

    def vprint(self, msg, tag=None):
        self.lines.append(f"{tag}: {msg}")

    def text(self):
        return "\n".join(self.lines)


def _sheet_without_et_columns(edit, name="Alice", birth="1970-01-15"):
    """Write a one-sheet workbook without the two columns; ``edit(df)`` fills it first."""
    p = _plan(name=name, birth=birth)
    p.zeroWagesAndContributions()
    df = p.timeLists[name].copy()
    edit(df)
    df = df.drop(columns=["gross earnings", "months worked"])
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    df.to_excel(tmp.name, sheet_name=name, index=False)
    return tmp.name


def _load(path, name="Alice", birth="1970-01-15"):
    p = _plan(name=name, birth=birth)
    p.mylog = _Log()
    p.readHFP(path)
    return p


def test_ui_sync_keeps_the_fallback_and_follows_wage_edits():
    """The UI re-reads its edited tables (``owlbridge._setContributions``
    → ``readHFP({iname: table})``), which carry every column. The earnings test must still
    see the wages after the sync, and wages edited afterwards (no frozen copy)."""

    def edit(df):
        df.loc[df.index[5:8], "anticipated wages"] = 80_000.0

    path = _sheet_without_et_columns(edit)
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


def test_absent_et_columns_are_not_reported_as_zero():
    """The two columns read as zero mean "taken from wages / 12 months", so the "treated
    as zero" notice must not list them (it still lists the others)."""

    def edit(df):
        df.loc[df.index[5], "anticipated wages"] = 80_000.0

    path = _sheet_without_et_columns(edit)
    try:
        p = _load(path)
        zero_lines = [line for line in p.mylog.lines if "treated as zero" in line]
        assert not any("gross earnings" in line or "months worked" in line for line in zero_lines)
    finally:
        os.unlink(path)


def _fallback_warnings(p, entitled_from):
    """Call the deferral warning the way step 3 will, and return its WARNING lines."""
    p.mylog = _Log()
    p._warnGrossEarningsFallback(entitled_from)
    return [line for line in p.mylog.lines if line.startswith("WARNING") and "gross earnings" in line]


def test_no_fallback_warning_without_wages_or_deferrals():
    """No WARNING for a workbook with no wages (a retiree), and none
    for years whose only contribution is an HSA (a payroll HSA is not in W-2 box 5)."""

    def retiree(df):
        pass

    def hsa_only(df):
        df.loc[df.index[5], "anticipated wages"] = 80_000.0
        df.loc[df.index[5], "HSA ctrb"] = 4_000.0

    for edit in (retiree, hsa_only):
        path = _sheet_without_et_columns(edit)
        try:
            assert not _fallback_warnings(_load(path), [thisyear])
        finally:
            os.unlink(path)


def test_fallback_warning_names_only_test_years():
    """The warning names years from the first year of entitlement up to the FRA year
    only (the test does not apply outside them). Alice, born 1970-01-15, reaches FRA (67)
    in 2037; entitled from thisyear + 1 here."""

    def edit(df):
        for n in (0, 1, 12):  # before entitlement, named, after the FRA year
            df.loc[df.index[5 + n], "anticipated wages"] = 80_000.0
            df.loc[df.index[5 + n], "401k ctrb"] = 10_000.0

    path = _sheet_without_et_columns(edit)
    try:
        warn = _fallback_warnings(_load(path), [thisyear + 1])
        assert len(warn) == 1
        assert str(thisyear + 1) in warn[0]
        assert str(thisyear) not in warn[0]
        assert str(thisyear + 12) not in warn[0]
        # Not entitled within the plan: nothing to warn about.
        assert not _fallback_warnings(_load(path), [None])
    finally:
        os.unlink(path)


def test_fallback_warning_without_a_workbook():
    """The deferral warning is about years where the test falls back to wages, whatever
    the reason: here a UI case with no workbook (all columns present, at zero)."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 80_000.0
    df.loc[df.index[5], "401k ctrb"] = 10_000.0
    p.readHFP({"Alice": df.copy()}, houseTables=False)
    warn = _fallback_warnings(p, [thisyear])
    assert len(warn) == 1
    assert str(thisyear) in warn[0]


def test_fallback_warning_on_a_plan_built_by_the_assistant():
    """The warning reads what the test reads, the
    plan arrays. The MCP assistant (``assistant/tools.py``) writes wages to ``omega_in``
    and contributions to ``kappa_ijn`` and leaves the tables at zero; the test then falls
    back to those wages, so the warning must name the year. ``kappa_ijn[i, 0]`` holds
    the taxable column, ``[i, 1]`` the 401k and IRA ones, ``[i, 2]`` the Roth 401k and Roth
    IRA ones; ``[i, 3]`` (HSA) is left out."""
    q = _plan()
    q.zeroWagesAndContributions()
    q.omega_in[0, :3] = 70_000.0
    q.kappa_ijn[0, 1, 0] = 10_000.0  # 401k / IRA
    q.kappa_ijn[0, 2, 1] = 6_000.0  # Roth 401k / Roth IRA
    q.kappa_ijn[0, 3, 2] = 4_000.0  # HSA only: not named
    warn = _fallback_warnings(q, [thisyear])
    assert len(warn) == 1
    assert str(thisyear) in warn[0] and str(thisyear + 1) in warn[0]
    assert str(thisyear + 2) not in warn[0]
    # A positive gross earnings entry is not a fallback.
    q.etEarnings_in[0, 0] = 85_000.0
    warn = _fallback_warnings(q, [thisyear])
    assert len(warn) == 1 and f"year(s) {thisyear + 1}:" in warn[0]


@pytest.mark.toml
def test_no_fallback_warning_at_hfp_read():
    """Loading an example and re-reading its tables the way the UI does gives no
    earnings-test warning. jack+jill: Jack has wages and a 401k contribution in 2026-2027."""
    from pathlib import Path

    case = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"
    p = owl.readConfig(str(case), verbose=False)
    p.mylog = _Log()
    p.readHFP({n: p.timeLists[n] for n in p.inames}, houseTables=False)
    assert not [line for line in p.mylog.lines if "gross earnings" in line]
    # ... while the warning itself still finds Jack's years when called.
    assert _fallback_warnings(p, [thisyear, None])


def test_blank_months_worked_cell_reads_as_zero():
    """A blank cell reads as zero like in every other column (Documentation: "leave it
    blank where it does not apply"); it used to stop the read with "cannot convert float
    NaN". Zero means the default: 12 in a year with earnings."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"].copy()
    df["months worked"] = df["months worked"].astype(float)
    df.loc[df.index[5], "gross earnings"] = 50_000.0
    df.loc[df.index[5], "months worked"] = 6
    df.loc[df.index[6], "gross earnings"] = 30_000.0
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
    """The example workbooks do not carry the two columns, so
    the test falls back to wages: Jill (jack+jill) has $85,000 of wages in 2028, which the
    earnings test must see."""
    from pathlib import Path

    case = Path(__file__).resolve().parents[2] / "examples" / "Case_jack+jill.toml"
    p = owl.readConfig(str(case), verbose=False)
    j = p.inames.index("Jill")
    n = 2028 - thisyear
    earnings, months = p._earnings_test_inputs()
    assert earnings[j, n] == pytest.approx(85_000.0)
    assert months[j, n] == 12


def test_fallback_warning_names_taxable_contribution_years():
    """*anticipated wages* are entered net of every *ctrb* column (HFP
    convention, Documentation), *taxable ctrb* included, and a taxable contribution is paid
    from W-2 box 5 wages. So a year with wages and only a taxable contribution is one where
    the fallback understates the test's earnings, and is named like a 401k year."""
    p = _plan()
    p.zeroWagesAndContributions()
    df = p.timeLists["Alice"]
    df.loc[df.index[5], "anticipated wages"] = 90_000.0
    df.loc[df.index[5], "taxable ctrb"] = 10_000.0
    p.setContributions()
    warn = _fallback_warnings(p, [thisyear])
    assert len(warn) == 1
    assert str(thisyear) in warn[0]
