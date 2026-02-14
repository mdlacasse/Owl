"""
DataframeRateModel creation

Tests verify that the Rates class correctly handles different rate methods
and generates rate series as expected.

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
########################################################################################
from owlplanner.rate_models.base import BaseRateModel
import numpy as np


class DataFrameRateModel(BaseRateModel):
    """
    Rate model that generates rates from a provided DataFrame.
    """

    model_name = "dataframe"
    description = "Time-indexed rates supplied via pandas DataFrame."

    required_parameters = {
        "df": {
            "type": "pandas.DataFrame",
            "description": "Must contain year, S&P 500, Bonds Baa, TNotes, Inflation"
        }
    }

    optional_parameters = {}

    @property
    def deterministic(self):
        return True
    
    @property
    def constant(self):
        return False


    def generate(self, N):

        df = self.config.get("df")

        if df is None:
            raise ValueError("DataFrame must be provided with the dataframe option.")

        # --------------------------------------------------
        # Normalize accepted column names
        # --------------------------------------------------

        column_map = {
            "S&P 500": "S&P 500",
            "Bonds Baa": "Bonds Baa",
            "Corporate Baa": "Bonds Baa",
            "TNotes": "TNotes",
            "T Bonds": "TNotes",
            "Inflation": "Inflation",
            "inflation": "Inflation",
        }

        required = ["year", "S&P 500", "Bonds Baa", "TNotes", "Inflation"]

        normalized = {}

        for col in required:
            if col == "year":
                if "year" not in df.columns:
                    raise ValueError("Missing column 'year' in DataFrame.")
                normalized["year"] = df["year"]
                continue

            # Find matching alias
            found = None
            for original, canonical in column_map.items():
                if original in df.columns and canonical == col:
                    found = original
                    break

            if found is None:
                raise ValueError(f"Missing required rate column for '{col}' in DataFrame.")

            normalized[col] = df[found]

        # --------------------------------------------------
        # Extract series
        # --------------------------------------------------

        data = np.column_stack([
            normalized["S&P 500"],
            normalized["Bonds Baa"],
            normalized["TNotes"],
            normalized["Inflation"],
        ])

        # If values look like percentages (>1), convert
        if np.nanmean(np.abs(data)) > 1:
            data = data / 100.0

        if data.shape[0] < N:
            raise ValueError("DataFrame does not contain enough rows for requested years.")

        return data[:N]
