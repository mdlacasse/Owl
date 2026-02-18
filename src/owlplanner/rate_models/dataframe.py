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
from owlplanner.rate_models.constants import REQUIRED_RATE_COLUMNS


class DataFrameRateModel(BaseRateModel):
    """
    Rate model that generates rates from a provided DataFrame.

    Rates are read sequentially from the DataFrame. Row order defines the
    sequence; no year column is used. Historical data with year indexing
    is handled by built-in methods (e.g. historical, histochastic) which
    read from the package's data directory.
    """

    model_name = "dataframe"
    description = "Sequential rates read from a pandas DataFrame (no year column)."

    required_parameters = {
        "df": {
            "type": "pandas.DataFrame",
            "description": "Must contain columns: ['S&P 500','Bonds Baa','TNotes','Inflation']",
        },
        "n_years": {
            "type": "int",
            "description": "Number of years (rows) required for plan horizon.",
        },
    }

    optional_parameters = {
        "offset": {
            "type": "int",
            "default": 0,
            "description": "Number of initial rows to skip before reading sequentially.",
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
        n_years = self.get_param("n_years")
        offset = int(self.get_param("offset") or 0)

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

        missing = [c for c in canonical_cols if c not in normalized]
        if missing:
            raise ValueError(
                f"DataFrame missing required columns: {missing}. "
                f"Required: {canonical_cols}"
            )

        # --------------------------------------------------
        # Validate row count: must have at least n_years + offset rows
        # --------------------------------------------------

        required_rows = n_years + offset
        if len(df) < required_rows:
            raise ValueError(
                f"DataFrame has {len(df)} rows but needs at least {required_rows} "
                f"(n_years={n_years} + offset={offset})."
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
