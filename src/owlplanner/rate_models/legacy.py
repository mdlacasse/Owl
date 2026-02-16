"""
Wrapper for legacy rate models.  All new rate models should subclass BaseRateModel.


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
from owlplanner import rates


class LegacyRateModel(BaseRateModel):

    model_name = "legacy"
    description = "Built-in OWL rate models."

    # --------------------------------------------------
    # Per-method metadata
    # --------------------------------------------------

    METHOD_METADATA = {

        # ------------------------------------------------------------
        # Deterministic Fixed Methods
        # ------------------------------------------------------------

        "default": {
            "description": "30-year trailing historical average deterministic rates.",
            "required_parameters": {},
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        "optimistic": {
            "description": "Optimistic fixed rates based on industry forecasts.",
            "required_parameters": {},
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        "conservative": {
            "description": "Conservative fixed rate assumptions.",
            "required_parameters": {},
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        "user": {
            "description": "User-specified fixed annual rates.",
            "required_parameters": {
                "values": {
                    "type": "list[float]",
                    "length": 4,
                    "description": "Rates in percent: [Stocks, Bonds Baa, TNotes, Inflation]",
                }
            },
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        # ------------------------------------------------------------
        # Historical Deterministic
        # ------------------------------------------------------------

        "historical": {
            "description": "Historical year-by-year returns starting at frm.",
            "required_parameters": {
                "frm": {
                    "type": "int",
                    "description": "Starting historical year (inclusive)."
                }
            },
            "optional_parameters": {
                "to": {
                    "type": "int",
                    "description": "Ending historical year (inclusive). Defaults to frm + N_n - 1."
                }
            },
            "deterministic": True,
            "constant": False,
        },

        "historical average": {
            "description": "Fixed rates equal to historical average over selected range.",
            "required_parameters": {
                "frm": {"type": "int"},
                "to": {"type": "int"},
            },
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        # ------------------------------------------------------------
        # Stochastic Models
        # ------------------------------------------------------------

        "stochastic": {
            "description": "Multivariate normal stochastic model using user-provided mean and volatility.",
            "required_parameters": {
                "values": {
                    "type": "list[float]",
                    "length": 4,
                    "description": "Mean returns in percent.",
                },
                "stdev": {
                    "type": "list[float]",
                    "length": 4,
                    "description": "Standard deviations in percent.",
                },
            },
            "optional_parameters": {
                "corr": {
                    "type": "4x4 matrix or list[6]",
                    "description": "Correlation matrix or upper-triangular off-diagonal list."
                }
            },
            "deterministic": False,
            "constant": False,
        },

        "histochastic": {
            "description": "Multivariate normal model using historical mean and covariance from selected range.",
            "required_parameters": {
                "frm": {"type": "int"},
                "to": {"type": "int"},
            },
            "optional_parameters": {},
            "deterministic": False,
            "constant": False,
        },

    }

    constant_methods = (
        "default",
        "optimistic",
        "conservative",
        "user",
        "historical average",
    )

    def __init__(self, config, seed=None, logger=None):
        super().__init__(config, seed, logger)

        self.method = config["method"]
        self.frm = config["frm"]
        self.to = config["to"]

        self._rates = rates.Rates(logger, seed=seed)

        self._rates.setMethod(
            self.method,
            self.frm,
            self.to,
            config.get("values"),
            config.get("stdev"),
            config.get("corr"),
        )

    @property
    def deterministic(self):
        # deterministic means no randomness
        return self.method in (
            "default",
            "optimistic",
            "conservative",
            "user",
            "historical average",
            "historical",
        )

    @property
    def constant(self):
        # constant means no time variation
        return self.method in self.constant_methods

    def generate(self, N):
        return self._rates.genSeries(N)

    @classmethod
    def get_method_metadata(cls, method):
        if method not in cls.METHOD_METADATA:
            raise ValueError(f"No metadata defined for legacy method '{method}'")

        meta = cls.METHOD_METADATA[method]

        return {
            "model_name": method,
            "description": meta["description"],
            "required_parameters": meta.get("required_parameters", {}),
            "optional_parameters": meta.get("optional_parameters", {}),
        }
