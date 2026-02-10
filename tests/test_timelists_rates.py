"""
Tests for timelists module to load Rates from HFP file

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


class TestHFPRatesWriteRead:
    """Tests for writing and reading HFP rates tab."""

    def test_hfp_rates_tab_loaded(self):
            """Test that Rates tab is loaded and converted correctly from HFP."""
            birth_year = 1980
            remaining_years = 10
            expectancy = (thisyear - birth_year) + remaining_years

            p = owl.Plan(
                ["Alice"],
                ["1980-01-15"],
                [expectancy],
                "Test HFP Rates",
                verbose=False
            )
            p.zeroContributions()

            max_horizon = remaining_years

            years = list(range(thisyear, thisyear + max_horizon + 1))

            rates_df = pd.DataFrame({
                "year": years,
                "S&P 500": ["5.5%"] * len(years),
                "Corporate Baa": [3.25] * len(years),
                "T Bonds": [0.0275] * len(years),
                "inflation": [2.8] * len(years),
            })

            p.rateTable = rates_df

            # Save HFP
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                wb = p.saveContributions()
                wb.save(tmp_path)

                # Read back
                p2 = owl.Plan(
                    ["Alice"],
                    ["1980-01-15"],
                    [expectancy],
                    "Test HFP Rates Read",
                    verbose=False
                )
                p2.readContributions(tmp_path)

                assert p2.rateTable is not None
                assert len(p2.rateTable) == len(rates_df)

                # Verify percent → decimal conversion
                row = p2.rateTable.iloc[0]
                assert abs(row["S&P 500"] - 0.055) < 1e-9
                assert abs(row["Corporate Baa"] - 0.0325) < 1e-9
                assert abs(row["T Bonds"] - 0.0275) < 1e-9
                assert abs(row["inflation"] - 0.028) < 1e-9

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    def test_hfp_without_rates_tab(self):
        """Test that HFP loads successfully when no Rates tab is present."""
        birth_year = 1980
        remaining_years = 10
        expectancy = (thisyear - birth_year) + remaining_years

        p = owl.Plan(
            ["Alice"],
            ["1980-01-15"],
            [expectancy],
            "Test HFP No Rates",
            verbose=False
        )
        p.zeroContributions()

        # IMPORTANT: Do NOT set p.rateTable
        assert p.rateTable is None

        # Save HFP (no Rates sheet should be written)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb = p.saveContributions()
            wb.save(tmp_path)

            # Read back
            p2 = owl.Plan(
                ["Alice"],
                ["1980-01-15"],
                [expectancy],
                "Test HFP No Rates Read",
                verbose=False
            )
            p2.readContributions(tmp_path)

            # Assertions
            assert p2.rateTable is None, "rateTable should be None when no Rates tab is present"

            # Sanity check: normal timelists still load
            assert "Alice" in p2.timeLists
            assert len(p2.timeLists["Alice"]) > 0

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_hfp_rates_missing_year_raises(self):
        """Rates tab must cover full planning horizon; missing years raise error."""
        birth_year = 1975
        remaining_years = 10
        expectancy = (thisyear - birth_year) + remaining_years

        p = owl.Plan(
            ["Carol"],
            ["1975-01-15"],
            [expectancy],
            "Missing Rates Year",
            verbose=False
        )
        p.zeroContributions()

        # Planning horizon: thisyear .. thisyear + remaining_years - 1
        start = thisyear
        end = thisyear + remaining_years

        # Deliberately omit one calendar year
        years = list(range(start, end))
        missing_year = thisyear + 5
        years.remove(missing_year)

        rates_df = pd.DataFrame({
            "year": years,
            "S&P 500": [5.5] * len(years),
            "Corporate Baa": [3.25] * len(years),
            "T Bonds": [0.0275] * len(years),
            "inflation": [2.8] * len(years),
        })

        p.rateTable = rates_df

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb = p.saveContributions()
            wb.save(tmp_path)

            p2 = owl.Plan(
                ["Carol"],
                ["1975-01-15"],
                [expectancy],
                "Missing Rates Year Read",
                verbose=False
            )

            try:
                p2.readContributions(tmp_path)
                assert False, "Expected failure due to missing Rates year"
            except Exception as e:
                msg = str(e)
                assert "Rates table missing years" in msg
                assert str(missing_year) in msg

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
