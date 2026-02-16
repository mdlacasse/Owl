"""
Wrapper for core builtin rate models.
All new rate models should subclass BaseRateModel.

Copyright (C) 2025-2026 The Owlplanner Authors
"""
###########################################################################
from owlplanner.rate_models.base import BaseRateModel
from owlplanner import rates


class BuiltinRateModel(BaseRateModel):

    model_name = "builtin"
    description = "Built-in OWL rate models."

    #######################################################################
    # Per-method metadata
    #######################################################################

    BUILTINS_METADATA = {

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
            "description": "User-specified fixed annual rates (percent).",
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
            "description": "Historical year-by-year returns over selected range.",
            "required_parameters": {
                "frm": {
                    "type": "int",
                    "description": "Starting historical year (inclusive)."
                },
            },
            "optional_parameters": {
                "to": {
                    "type": "int",
                    "description": "Ending historical year (inclusive). "
                                   "Defaults to frm if not provided."
                },
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
                    "description": ("Pearson correlation coefficient (-1 to 1)."
                                    " Matrix or upper-triangle off-diagonals. Standard in finance/statistics."),
                }
            },
            "deterministic": False,
            "constant": False,
        },

        "histochastic": {
            "description": "Multivariate normal model using historical mean and covariance.",
            "required_parameters": {
                "frm": {"type": "int"},
                "to": {"type": "int"},
            },
            "optional_parameters": {},
            "deterministic": False,
            "constant": False,
        },
    }

    #######################################################################
    # Initialization
    #######################################################################

    def __init__(self, config, seed=None, logger=None):

        self.method = config["method"]

        if self.method not in self.BUILTINS_METADATA:
            raise ValueError(f"Unknown builtin rate method '{self.method}'.")

        # Inject metadata into base validation system
        meta = self.BUILTINS_METADATA[self.method]
        self.required_parameters = meta.get("required_parameters", {})
        self.optional_parameters = meta.get("optional_parameters", {})

        # Run centralized validation
        super().__init__(config, seed, logger)

        # Extract normalized parameters
        frm = self.get_param("frm")
        to = self.get_param("to")
        values = self.get_param("values")
        stdev = self.get_param("stdev")
        corr = self.get_param("corr")

        # Special-case: historical single-year fallback
        if self.method == "historical" and frm is not None and to is None:
            to = frm

        # Initialize underlying Rates engine
        self._rates = rates.Rates(logger, seed=seed)

        self._rates.setMethod(
            self.method,
            frm,
            to,
            values,
            stdev,
            corr,
        )

    #######################################################################
    # Model properties
    #######################################################################

    @property
    def deterministic(self):
        return self.BUILTINS_METADATA[self.method]["deterministic"]

    @property
    def constant(self):
        return self.BUILTINS_METADATA[self.method]["constant"]

    #######################################################################
    # Generate
    #######################################################################

    def generate(self, N):
        return self._rates.genSeries(N)

    #######################################################################
    # Metadata helpers
    #######################################################################

    @classmethod
    def get_method_metadata(cls, method):
        if method not in cls.BUILTINS_METADATA:
            raise ValueError(f"No metadata defined for builtin method '{method}'")

        meta = cls.BUILTINS_METADATA[method]

        return {
            "model_name": method,
            "description": meta["description"],
            "required_parameters": meta.get("required_parameters", {}),
            "optional_parameters": meta.get("optional_parameters", {}),
        }

    @classmethod
    def list_methods(cls):
        return set(cls.BUILTINS_METADATA.keys())
