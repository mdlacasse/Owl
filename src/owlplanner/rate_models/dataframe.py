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
            "description": "Must contain columns: ['S&P 500','Bonds Baa','T-Notes','Inflation']",
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
        "in_percent": {
            "type": "bool",
            "default": True,
            "description": (
                "If True (default), DataFrame values are in percent (e.g. 7.0 = 7%) "
                "and are divided by 100 internally. Pass False if values are already "
                "in decimal (e.g. 0.07 = 7%)."
            ),
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
        # Validate required columns (exact names, no aliases)
        # --------------------------------------------------

        missing = [c for c in REQUIRED_RATE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"DataFrame missing required columns: {missing}. "
                f"Required: {list(REQUIRED_RATE_COLUMNS)}"
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

        data = df[list(REQUIRED_RATE_COLUMNS)].values.astype(float)

        if offset < 0:
            raise ValueError("offset must be >= 0.")

        if offset + N > data.shape[0]:
            raise ValueError(
                f"DataFrame does not contain enough rows for offset={offset} and N={N}."
            )

        data = data[offset:offset + N]

        in_percent = self.get_param("in_percent")
        if not isinstance(in_percent, bool):
            raise ValueError(
                f"'in_percent' must be a bool (True or False), got {type(in_percent).__name__!r}."
            )
        if in_percent:
            data = data / 100.0

        return data
