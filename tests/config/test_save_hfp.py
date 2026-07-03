"""
Tests for Plan.saveHFP() - writing the Household Financial Profile workbook.

saveHFP() is the write counterpart of readHFP(). These tests verify:
  - round-trip fidelity for plans populated through timeLists (readHFP path)
  - reconstruction from internal arrays for programmatically built plans
  - default file naming (HFP_<name>.xlsx) and hfpFileName update

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
import pandas as pd
import pytest

import owlplanner as owl
from owlplanner.hfp_io import conditionDebtsAndFixedAssetsDF

thisyear = date.today().year


def _make_plan(name, remaining_years=30):
    birth_year = 1970
    expectancy = (thisyear - birth_year) + remaining_years
    return owl.Plan(["Alice"], ["1970-01-15"], [expectancy], name, verbose=False)


def _make_couple(name, remaining_years=(30, 25)):
    birth_years = [1970, 1972]
    expectancies = [(thisyear - by) + ry for by, ry in zip(birth_years, remaining_years, strict=True)]
    return owl.Plan(["Alice", "Bob"], ["1970-01-15", "1972-06-30"], expectancies, name, verbose=False)


class TestSaveHFPRoundTrip:
    """Round-trip through saveHFP() -> readHFP() preserves plan inputs."""

    def test_roundtrip_from_timelists(self, tmp_path):
        p1 = _make_plan("RT Plan")
        p1.zeroWagesAndContributions()
        df = p1.timeLists["Alice"]
        df.loc[df["year"] == thisyear, "anticipated wages"] = 100_000
        df.loc[df["year"] == thisyear + 1, "anticipated wages"] = 105_000
        df.loc[df["year"] == thisyear, "401k ctrb"] = 20_000
        df.loc[df["year"] == thisyear, "IRA ctrb"] = 7_000
        df.loc[df["year"] == thisyear + 1, "Roth 401k ctrb"] = 10_000
        df.loc[df["year"] == thisyear + 2, "Roth IRA ctrb"] = 7_000
        df.loc[df["year"] == thisyear, "HSA ctrb"] = 4_000
        df.loc[df["year"] == thisyear + 3, "Roth conv"] = 50_000
        df.loc[df["year"] == thisyear - 2, "Roth conv"] = 25_000
        df.loc[df["year"] == thisyear + 5, "big-ticket items"] = -30_000
        df.loc[df["year"] == thisyear + 1, "other inc"] = 12_000
        df.loc[df["year"] == thisyear + 1, "net inv"] = 3_000
        p1.setContributions()

        fname = str(tmp_path / "HFP_rt.xlsx")
        saved = p1.saveHFP(fname, overwrite=True)
        assert saved == fname

        p2 = _make_plan("RT Plan 2")
        p2.readHFP(fname)

        np.testing.assert_allclose(p2.omega_in, p1.omega_in)
        np.testing.assert_allclose(p2.other_inc_in, p1.other_inc_in)
        np.testing.assert_allclose(p2.netinv_in, p1.netinv_in)
        np.testing.assert_allclose(p2.Lambda_in, p1.Lambda_in)
        np.testing.assert_allclose(p2.kappa_ijn, p1.kappa_ijn)
        np.testing.assert_allclose(p2.myRothX_in, p1.myRothX_in)

    def test_roundtrip_timelists_preserve_column_split(self, tmp_path):
        """The 401k/IRA and Roth 401k/Roth IRA column splits survive when timeLists exist."""
        p1 = _make_plan("Split Plan")
        p1.zeroWagesAndContributions()
        df = p1.timeLists["Alice"]
        df.loc[df["year"] == thisyear, "401k ctrb"] = 20_000
        df.loc[df["year"] == thisyear, "IRA ctrb"] = 7_000
        p1.setContributions()

        fname = str(tmp_path / "HFP_split.xlsx")
        p1.saveHFP(fname, overwrite=True)

        p2 = _make_plan("Split Plan 2")
        p2.readHFP(fname)
        df2 = p2.timeLists["Alice"]
        row = df2[df2["year"] == thisyear]
        assert row["401k ctrb"].iloc[0] == pytest.approx(20_000)
        assert row["IRA ctrb"].iloc[0] == pytest.approx(7_000)

    def test_roundtrip_debts_and_fixed_assets(self, tmp_path):
        p1 = _make_plan("House Plan")
        p1.zeroWagesAndContributions()
        p1.setContributions()
        debts = pd.DataFrame(
            {
                "active": [True],
                "name": ["mortgage"],
                "type": ["mortgage"],
                "year": [thisyear - 3],
                "term": [30],
                "amount": [300_000.0],
                "rate": [3.5],
            }
        )
        assets = pd.DataFrame(
            {
                "active": [True, False],
                "name": ["house", "cabin"],
                "type": ["residence", "real estate"],
                "year": [thisyear, thisyear],
                "basis": [350_000.0, 100_000.0],
                "value": [700_000.0, 200_000.0],
                "rate": [3.0, 2.0],
                "yod": [thisyear + 8, thisyear + 12],
                "commission": [5.0, 5.0],
            }
        )
        p1.houseLists["Debts"] = conditionDebtsAndFixedAssetsDF(debts, "Debts")
        p1.houseLists["Fixed Assets"] = conditionDebtsAndFixedAssetsDF(assets, "Fixed Assets")

        fname = str(tmp_path / "HFP_house.xlsx")
        p1.saveHFP(fname, overwrite=True)

        p2 = _make_plan("House Plan 2")
        p2.readHFP(fname)
        debts2 = p2.houseLists["Debts"]
        assets2 = p2.houseLists["Fixed Assets"]
        assert len(debts2) == 1
        assert debts2["name"].iloc[0] == "mortgage"
        assert debts2["amount"].iloc[0] == pytest.approx(300_000)
        assert debts2["rate"].iloc[0] == pytest.approx(3.5)
        assert len(assets2) == 2
        assert list(assets2["active"]) == [True, False]
        assert assets2["value"].iloc[0] == pytest.approx(700_000)


class TestSaveHFPProgrammatic:
    """Plans populated directly through arrays (no timeLists) are reconstructed."""

    def test_arrays_roundtrip(self, tmp_path):
        p1 = _make_couple("Prog Plan")
        # Constructor pre-populates zeroed timeLists; writing into the arrays
        # makes them stale, and saveHFP must rebuild them from the arrays.
        p1.omega_in[0, 0:4] = 90_000
        p1.omega_in[1, 0:2] = 60_000
        p1.other_inc_in[0, 1] = 15_000
        p1.netinv_in[1, 0] = 2_500
        p1.Lambda_in[0, 5] = -40_000
        p1.kappa_ijn[0, 0, 0] = 5_000
        p1.kappa_ijn[0, 1, 0:3] = 23_000
        p1.kappa_ijn[1, 2, 0:2] = 7_000
        p1.kappa_ijn[0, 3, 0] = 4_300
        p1.myRothX_in[0, 2] = 30_000
        # Lead-in years (5-year Roth maturation window) live in the last 5 slots.
        p1.myRothX_in[0, p1.N_n + 3] = 10_000
        p1.kappa_ijn[1, 2, p1.N_n + 4] = 6_500

        fname = str(tmp_path / "HFP_prog.xlsx")
        saved = p1.saveHFP(fname, overwrite=True)
        assert saved == fname
        # Reconstructed time lists are stored on the plan and reflect the arrays.
        assert p1.timeLists["Alice"]["anticipated wages"].iloc[5] == pytest.approx(90_000)

        p2 = _make_couple("Prog Plan 2")
        p2.readHFP(fname)

        np.testing.assert_allclose(p2.omega_in, p1.omega_in)
        np.testing.assert_allclose(p2.other_inc_in, p1.other_inc_in)
        np.testing.assert_allclose(p2.netinv_in, p1.netinv_in)
        np.testing.assert_allclose(p2.Lambda_in, p1.Lambda_in)
        np.testing.assert_allclose(p2.kappa_ijn, p1.kappa_ijn)
        np.testing.assert_allclose(p2.myRothX_in, p1.myRothX_in)

    def test_existing_timelists_take_precedence(self, tmp_path):
        """When timeLists agree with the arrays, saveHFP writes them as-is (no reconstruction)."""
        p1 = _make_plan("Prec Plan")
        p1.zeroWagesAndContributions()
        df = p1.timeLists["Alice"]
        df.loc[df["year"] == thisyear, "IRA ctrb"] = 7_000
        p1.setContributions()

        fname = str(tmp_path / "HFP_prec.xlsx")
        p1.saveHFP(fname, overwrite=True)

        read_df = pd.read_excel(fname, sheet_name="Alice")
        row = read_df[read_df["year"] == thisyear]
        assert row["IRA ctrb"].iloc[0] == pytest.approx(7_000)
        assert row["401k ctrb"].iloc[0] == pytest.approx(0)

    def test_stale_timelists_are_rebuilt(self, tmp_path):
        """Arrays modified after setContributions win over the stale timeLists."""
        p1 = _make_plan("Stale Plan")
        p1.zeroWagesAndContributions()
        df = p1.timeLists["Alice"]
        df.loc[df["year"] == thisyear, "anticipated wages"] = 50_000
        p1.setContributions()
        p1.omega_in[0, 0] = 80_000  # Diverge from timeLists.

        fname = str(tmp_path / "HFP_stale.xlsx")
        p1.saveHFP(fname, overwrite=True)

        read_df = pd.read_excel(fname, sheet_name="Alice")
        row = read_df[read_df["year"] == thisyear]
        assert row["anticipated wages"].iloc[0] == pytest.approx(80_000)

    def test_hsa_medicare_clip_does_not_flag_stale(self, tmp_path):
        """HSA contributions past Medicare enrollment are clipped in the arrays by
        setContributions(); this must not cause saveHFP to discard the timeLists
        (which would lose the 401k/IRA column split)."""
        p1 = _make_plan("HSA Plan")
        p1.zeroWagesAndContributions()
        df = p1.timeLists["Alice"]
        # Alice (born 1970) enrolls in Medicare in 2035; entry beyond that is clipped in arrays.
        df.loc[df["year"] == thisyear + 15, "HSA ctrb"] = 4_000
        df.loc[df["year"] == thisyear, "IRA ctrb"] = 7_000
        p1.setContributions()
        assert p1.kappa_ijn[0, 3, 15] == pytest.approx(0)  # Clipped in arrays.

        fname = str(tmp_path / "HFP_hsa.xlsx")
        p1.saveHFP(fname, overwrite=True)

        read_df = pd.read_excel(fname, sheet_name="Alice")
        # Column split preserved: timeLists were not discarded.
        row = read_df[read_df["year"] == thisyear]
        assert row["IRA ctrb"].iloc[0] == pytest.approx(7_000)
        assert row["401k ctrb"].iloc[0] == pytest.approx(0)
        # Post-Medicare HSA entry preserved as input (re-clipped on read).
        row = read_df[read_df["year"] == thisyear + 15]
        assert row["HSA ctrb"].iloc[0] == pytest.approx(4_000)


class TestSaveHFPNaming:
    """Default file naming and hfpFileName bookkeeping."""

    def test_default_filename_from_plan_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p = _make_plan("myname")
        p.zeroWagesAndContributions()
        p.setContributions()
        saved = p.saveHFP(overwrite=True)
        assert saved == "HFP_myname.xlsx"
        assert (tmp_path / "HFP_myname.xlsx").is_file()
        assert p.hfpFileName == "HFP_myname.xlsx"

    def test_basename_with_hfp_prefix_not_doubled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p = _make_plan("prefixed")
        p.zeroWagesAndContributions()
        p.setContributions()
        saved = p.saveHFP("HFP_custom", overwrite=True)
        assert saved == "HFP_custom.xlsx"

    def test_explicit_filename_used_verbatim(self, tmp_path):
        p = _make_plan("verbatim")
        p.zeroWagesAndContributions()
        p.setContributions()
        fname = str(tmp_path / "somefile.xlsx")
        saved = p.saveHFP(fname, overwrite=True)
        assert saved == fname
        assert p.hfpFileName == fname
