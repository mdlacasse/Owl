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
###########################################################################
import numpy as np

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rates import REQUIRED_RATE_COLUMNS


class DataFrameRateModel(BaseRateModel):
    """
    Rate model that generates rates from a provided DataFrame.
    """

    model_name = "dataframe"
    description = "Sequential or year-based rates read from a pandas DataFrame."

    required_parameters = {
        "df": {
            "type": "pandas.DataFrame",
            "description": "Must contain columns: ['S&P 500','Bonds Baa','TNotes','Inflation']",
        },
        "n_years": {
            "type": "int",
            "description": "Number of years required for plan horizon.",
        },
    }

    optional_parameters = {
        "offset": {
            "type": "int",
            "default": 0,
            "description": "Number of initial rows to skip before reading sequentially.",
        },
        "frm": {
            "type": "int",
            "description": "Starting year (if year column present).",
        },
        "to": {
            "type": "int",
            "description": "Ending year (if year column present).",
        },
    }

    #######################################################################
    # Properties
    #######################################################################

    @property
    def deterministic(self):
        return True

    @property
    def constant(self):
        return False

    #######################################################################
    # Generate
    #######################################################################

    def generate(self, N):

        df = self.get_param("df")
        _ = self.get_param("n_years")  # validated by config
        offset = int(self.get_param("offset") or 0)
        frm = self.get_param("frm")
        to = self.get_param("to")

        # --------------------------------------------------
        # Normalize column names (supports aliases)
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

        canonical_cols = list(REQUIRED_RATE_COLUMNS)

        normalized = {}

        for canonical in canonical_cols:
            found = None
            for original, mapped in column_map.items():
                if original in df.columns and mapped == canonical:
                    found = original
                    break
            if found is not None:
                normalized[canonical] = df[found]

        # --------------------------------------------------
        # Year-based mode
        # --------------------------------------------------

        if "year" in df.columns or "Year" in df.columns:

            if frm is None or to is None:
                raise ValueError(
                    "frm and to must be provided when DataFrame contains a year column."
                )

            if frm > to:
                raise ValueError(f"frm ({frm}) must be <= to ({to}).")

            year_col = "year" if "year" in df.columns else "Year"

            missing = [c for c in canonical_cols if c not in normalized]
            if missing:
                raise ValueError(
                    f"DataFrame missing required columns: {missing}. "
                    f"Required: {canonical_cols}"
                )

            years = df[year_col].values

            try:
                years_int = years.astype(int)
            except Exception:
                raise ValueError("Year column must contain integers.")

            if len(np.unique(years_int)) != len(years_int):
                raise ValueError("Year column must contain unique values.")

            required_years = set(range(frm, to + 1))
            df_years = set(years_int)
            missing_years = sorted(required_years - df_years)

            if missing_years:
                raise ValueError(
                    f"DataFrame missing required years: {missing_years[:10]}"
                )

            df_sorted = df.set_index(year_col).sort_index()

            data = np.column_stack([
                df_sorted.loc[frm:to, normalized["S&P 500"].name],
                df_sorted.loc[frm:to, normalized["Bonds Baa"].name],
                df_sorted.loc[frm:to, normalized["TNotes"].name],
                df_sorted.loc[frm:to, normalized["Inflation"].name],
            ]).astype(float)

            if np.nanmean(np.abs(data)) > 1:
                data = data / 100.0

            if data.shape[0] < N:
                raise ValueError(
                    "DataFrame does not contain enough rows for requested years."
                )

            return data[:N]

        # --------------------------------------------------
        # Sequential mode (no year column)
        # --------------------------------------------------

        missing = [c for c in canonical_cols if c not in normalized]
        if missing:
            raise ValueError(
                f"DataFrame missing required columns: {missing}. "
                f"Required: {canonical_cols}"
            )

        data = np.column_stack([
            normalized["S&P 500"],
            normalized["Bonds Baa"],
            normalized["TNotes"],
            normalized["Inflation"],
        ]).astype(float)

        if offset < 0:
            raise ValueError("offset must be >= 0.")

        if offset + N > data.shape[0]:
            raise ValueError(
                f"DataFrame does not contain enough rows for offset={offset} and N={N}."
            )

        data = data[offset:offset + N]

        if np.nanmean(np.abs(data)) > 1:
            data = data / 100.0

        return data
