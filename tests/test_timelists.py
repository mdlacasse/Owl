"""
Tests for timelists module - HFP file reading and writing.

Tests verify that Household Financial Profile (HFP) files can be
saved and read back correctly, with special attention to the "active"
column which must be preserved as boolean values.

Copyright (C) 2025-2026 The Owlplanner Authors

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

import pandas as pd
import tempfile
import os
from datetime import date

import owlplanner as owl

# Get current year for calculating life expectancies
thisyear = date.today().year


class TestHFPWriteRead:
    """Tests for writing and reading HFP files."""

    def test_write_read_basic_hfp(self):
        """Test basic write and read of HFP file with wages and contributions."""
        # Create a simple plan
        # Expectancy = (current year - birth year) + remaining years
        birth_year = 1970
        remaining_years = 30
        expectancy = (thisyear - birth_year) + remaining_years
        p = owl.Plan(
            ["Alice"],
            ["1970-01-15"],
            [expectancy],
            "Test Plan",
            verbose=False
        )

        # Set some basic contributions
        p.zeroWagesAndContributions()
        alice_df = p.timeLists["Alice"]
        # Set some wages for a few years
        alice_df.loc[alice_df["year"] == 2025, "anticipated wages"] = 100_000
        alice_df.loc[alice_df["year"] == 2026, "anticipated wages"] = 105_000
        p.setContributions()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb = p.saveContributions()
            wb.save(tmp_path)

            # Read it back
            p2 = owl.Plan(
                ["Alice"],
                ["1970-01-15"],
                [expectancy],
                "Test Plan 2",
                verbose=False
            )
            p2.readHFP(tmp_path)

            # Verify data was preserved
            assert p2.timeLists is not None
            assert "Alice" in p2.timeLists
            alice_df2 = p2.timeLists["Alice"]
            assert alice_df2.loc[alice_df2["year"] == 2025, "anticipated wages"].iloc[0] == 100_000
            assert alice_df2.loc[alice_df2["year"] == 2026, "anticipated wages"].iloc[0] == 105_000

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_write_read_debts_with_active_column(self):
        """Test that debts with active column are preserved correctly."""
        # Create a plan
        birth_year = 1980
        remaining_years = 25
        expectancy = (thisyear - birth_year) + remaining_years
        p = owl.Plan(
            ["Bob"],
            ["1980-01-15"],
            [expectancy],
            "Test Debts",
            verbose=False
        )

        # Create debts DataFrame with active column
        debts_df = pd.DataFrame([
            {
                "active": True,
                "name": "Mortgage",
                "type": "mortgage",
                "year": 2020,
                "term": 30,
                "amount": 200_000,
                "rate": 4.5
            },
            {
                "active": False,
                "name": "Old Loan",
                "type": "loan",
                "year": 2015,
                "term": 10,
                "amount": 50_000,
                "rate": 5.0
            }
        ])

        # Set up houseLists
        p.houseLists = {"Debts": debts_df}
        p.zeroWagesAndContributions()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb = p.saveContributions()
            wb.save(tmp_path)

            # Read it back
            p2 = owl.Plan(
                ["Bob"],
                ["1980-01-15"],
                [expectancy],
                "Test Debts 2",
                verbose=False
            )
            p2.readHFP(tmp_path)

            # Verify debts were preserved
            assert "Debts" in p2.houseLists
            debts_df2 = p2.houseLists["Debts"]
            assert len(debts_df2) == 2

            # Verify active column is boolean
            assert debts_df2["active"].dtype == bool

            # Verify values are correct
            mortgage = debts_df2[debts_df2["name"] == "Mortgage"].iloc[0]
            assert mortgage["active"]
            assert mortgage["amount"] == 200_000

            old_loan = debts_df2[debts_df2["name"] == "Old Loan"].iloc[0]
            assert not old_loan["active"]
            assert old_loan["amount"] == 50_000

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_write_read_fixed_assets_with_active_column(self):
        """Test that fixed assets with active column are preserved correctly."""
        # Create a plan
        birth_year = 1975
        remaining_years = 30
        expectancy = (thisyear - birth_year) + remaining_years
        p = owl.Plan(
            ["Carol"],
            ["1975-01-15"],
            [expectancy],
            "Test Fixed Assets",
            verbose=False
        )

        # Create fixed assets DataFrame with active column and year (acquisition year)
        assets_df = pd.DataFrame([
            {
                "active": True,
                "name": "House",
                "type": "residence",
                "year": thisyear,  # Acquired in current year
                "basis": 150_000,
                "value": 300_000,
                "rate": 3.0,
                "yod": 2035,
                "commission": 6.0
            },
            {
                "active": False,
                "name": "Collectible",
                "type": "collectibles",
                "year": thisyear + 2,  # Acquired in future year
                "basis": 10_000,
                "value": 15_000,
                "rate": 2.0,
                "yod": 2030,
                "commission": 10.0
            }
        ])

        # Set up houseLists
        p.houseLists = {"Fixed Assets": assets_df}
        p.zeroWagesAndContributions()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb = p.saveContributions()
            wb.save(tmp_path)

            # Read it back
            p2 = owl.Plan(
                ["Carol"],
                ["1975-01-15"],
                [expectancy],
                "Test Fixed Assets 2",
                verbose=False
            )
            p2.readHFP(tmp_path)

            # Verify fixed assets were preserved
            assert "Fixed Assets" in p2.houseLists
            assets_df2 = p2.houseLists["Fixed Assets"]
            assert len(assets_df2) == 2

            # Verify active column is boolean
            assert assets_df2["active"].dtype == bool

            # Verify values are correct
            house = assets_df2[assets_df2["name"] == "House"].iloc[0]
            assert house["active"]
            assert house["value"] == 300_000
            assert house["year"] == thisyear  # Verify year column is preserved

            collectible = assets_df2[assets_df2["name"] == "Collectible"].iloc[0]
            assert not collectible["active"]
            assert collectible["value"] == 15_000
            assert collectible["year"] == thisyear + 2  # Verify year column is preserved

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_active_column_string_conversion(self):
        """Test that active column is correctly converted from strings."""
        # Create debts with string values for active (simulating Excel reading)
        debts_data = {
            "active": ["True", "False", "true", "false", "1", "0"],
            "name": ["Loan1", "Loan2", "Loan3", "Loan4", "Loan5", "Loan6"],
            "type": ["loan"] * 6,
            "year": [2020] * 6,
            "term": [10] * 6,
            "amount": [10_000] * 6,
            "rate": [5.0] * 6
        }
        debts_df = pd.DataFrame(debts_data)

        # Use conditionDebtsAndFixedAssetsDF to process it
        from owlplanner import timelists
        processed_df = timelists.conditionDebtsAndFixedAssetsDF(debts_df, "Debts")

        # Verify all active values are boolean
        assert processed_df["active"].dtype == bool

        # Verify conversions
        assert processed_df.loc[0, "active"]  # "True"
        assert not processed_df.loc[1, "active"]  # "False"
        assert processed_df.loc[2, "active"]  # "true"
        assert not processed_df.loc[3, "active"]  # "false"
        assert processed_df.loc[4, "active"]  # "1"
        assert not processed_df.loc[5, "active"]  # "0"

    def test_active_column_numeric_conversion(self):
        """Test that active column is correctly converted from numbers."""
        # Create debts with numeric values for active (simulating Excel reading)
        debts_data = {
            "active": [1, 0, 1.0, 0.0],
            "name": ["Loan1", "Loan2", "Loan3", "Loan4"],
            "type": ["loan"] * 4,
            "year": [2020] * 4,
            "term": [10] * 4,
            "amount": [10_000] * 4,
            "rate": [5.0] * 4
        }
        debts_df = pd.DataFrame(debts_data)

        # Use conditionDebtsAndFixedAssetsDF to process it
        from owlplanner import timelists
        processed_df = timelists.conditionDebtsAndFixedAssetsDF(debts_df, "Debts")

        # Verify all active values are boolean
        assert processed_df["active"].dtype == bool

        # Verify conversions
        assert processed_df.loc[0, "active"]  # 1
        assert not processed_df.loc[1, "active"]  # 0
        assert processed_df.loc[2, "active"]  # 1.0
        assert not processed_df.loc[3, "active"]  # 0.0

    def test_active_column_nan_defaults_to_true(self):
        """Test that NaN values in active column default to True."""
        # Create debts with NaN values for active
        debts_data = {
            "active": [True, None, pd.NA, False],
            "name": ["Loan1", "Loan2", "Loan3", "Loan4"],
            "type": ["loan"] * 4,
            "year": [2020] * 4,
            "term": [10] * 4,
            "amount": [10_000] * 4,
            "rate": [5.0] * 4
        }
        debts_df = pd.DataFrame(debts_data)

        # Use conditionDebtsAndFixedAssetsDF to process it
        from owlplanner import timelists
        processed_df = timelists.conditionDebtsAndFixedAssetsDF(debts_df, "Debts")

        # Verify all active values are boolean
        assert processed_df["active"].dtype == bool

        # Verify NaN/None default to True
        assert processed_df.loc[0, "active"]  # True
        assert processed_df.loc[1, "active"]  # None -> True
        assert processed_df.loc[2, "active"]  # pd.NA -> True
        assert not processed_df.loc[3, "active"]  # False

    def test_write_read_married_couple(self):
        """Test write and read for married couple with both having data."""
        # Create a plan for married couple
        birth_years = [1970, 1972]
        remaining_years = [30, 28]
        expectancy = [(thisyear - by) + ry for by, ry in zip(birth_years, remaining_years)]
        p = owl.Plan(
            ["George", "Gina"],
            ["1970-01-15", "1972-03-20"],
            expectancy,
            "Test Married",
            verbose=False
        )

        # Set contributions for both
        p.zeroWagesAndContributions()
        george_df = p.timeLists["George"]
        gina_df = p.timeLists["Gina"]

        george_df.loc[george_df["year"] == 2025, "anticipated wages"] = 120_000
        gina_df.loc[gina_df["year"] == 2025, "anticipated wages"] = 80_000

        p.setContributions()

        # Add debts
        debts_df = pd.DataFrame([
            {
                "active": True,
                "name": "Joint Mortgage",
                "type": "mortgage",
                "year": 2020,
                "term": 30,
                "amount": 300_000,
                "rate": 4.0
            }
        ])
        p.houseLists = {"Debts": debts_df}

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb = p.saveContributions()
            wb.save(tmp_path)

            # Read it back
            p2 = owl.Plan(
                ["George", "Gina"],
                ["1970-01-15", "1972-03-20"],
                expectancy,
                "Test Married 2",
                verbose=False
            )
            p2.readHFP(tmp_path)

            # Verify both individuals' data
            assert "George" in p2.timeLists
            assert "Gina" in p2.timeLists
            assert p2.timeLists["George"].loc[
                p2.timeLists["George"]["year"] == 2025, "anticipated wages"
            ].iloc[0] == 120_000
            assert p2.timeLists["Gina"].loc[
                p2.timeLists["Gina"]["year"] == 2025, "anticipated wages"
            ].iloc[0] == 80_000

            # Verify debts
            assert "Debts" in p2.houseLists
            assert len(p2.houseLists["Debts"]) == 1
            assert p2.houseLists["Debts"]["active"].dtype == bool

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
