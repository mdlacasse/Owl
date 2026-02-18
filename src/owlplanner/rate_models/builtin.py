"""
Wrapper for core builtin rate models.
All new rate models should subclass BaseRateModel.

Copyright (C) 2025-2026 The Owlplanner Authors
"""
###########################################################################
import numpy as np

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rate_models import _builtin_impl as impl
from owlplanner.rate_models.constants import (
    FIXED_PRESET_METHODS,
    HISTORICAL_RANGE_METHODS,
)


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
            "more_info" : None,
            "required_parameters": {},
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        "optimistic": {
            "description": "Optimistic fixed rates based on industry forecasts.",
            "more_info" : None,
            "required_parameters": {},
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        "conservative": {
            "description": "Conservative fixed rate assumptions.",
            "more_info" : None,
            "required_parameters": {},
            "optional_parameters": {},
            "deterministic": True,
            "constant": True,
        },

        "user": {
            "description": "User-specified fixed annual rates (percent).",
            "more_info" : None,
            "required_parameters": {
                "values": {
                    "type": "list[float]",
                    "length": 4,
                    "description": "Rates in percent: [Stocks, Bonds Baa, T-Notes, Inflation]",
                    "example": "[7.0, 4.5, 3.5, 2.5]",
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
            "more_info" : None,
            "required_parameters": {
                "frm": {
                    "type": "int",
                    "description": "Starting historical year (inclusive).",
                    "example": "1969",
                },
            },
            "optional_parameters": {
                "to": {
                    "type": "int",
                    "description": (
                        "Ending historical year (inclusive). "
                        "Defaults to frm if not provided."
                    ),
                    "example": "2002",
                },
            },
            "deterministic": True,
            "constant": False,
        },

        "historical average": {
            "description": "Fixed rates equal to historical average over selected range.",
            "more_info" : None,
            "required_parameters": {
                "frm": {
                    "type": "int",
                    "example": "1969",
                },
                "to": {
                    "type": "int",
                    "example": "2002",
                },
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
            "more_info" : None,
            "required_parameters": {
                "values": {
                    "type": "list[float]",
                    "length": 4,
                    "description": "Mean returns in percent.",
                    "example": "[7.0, 4.5, 3.5, 2.5]",
                },
                "stdev": {
                    "type": "list[float]",
                    "length": 4,
                    "description": "Standard deviations in percent.",
                    "example": "[17.0, 8.0, 6.0, 2.0]",
                },
            },
            "optional_parameters": {
                "corr": {
                    "type": "4x4 matrix or list[6]",
                    "description": (
                        "Pearson correlation coefficient (-1 to 1). "
                        "Matrix or upper-triangle off-diagonals. Standard in finance/statistics."
                    ),
                    "example": "[0.2, 0.1, 0.0, 0.3, 0.1, 0.2]",
                }
            },
            "deterministic": False,
            "constant": False,
        },

        "histochastic": {
            "description": "Multivariate normal model using historical mean and covariance.",
            "more_info" : None,
            "required_parameters": {
                "frm": {
                    "type": "int",
                    "example": "1969",
                },
                "to": {
                    "type": "int",
                    "example": "2002",
                },
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
        # Accept config-style names (standard_deviations, correlations) or API names (stdev, corr)
        config = dict(config or {})
        if "standard_deviations" in config and "stdev" not in config:
            config["stdev"] = config.pop("standard_deviations")
        if "correlations" in config and "corr" not in config:
            config["corr"] = config.pop("correlations")

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

        # Seed and RNG for stochastic methods
        rate_seed = config.get("rate_seed", seed)
        self._rng = np.random.default_rng(rate_seed)

        # Historical range default and validation
        if self.method in HISTORICAL_RANGE_METHODS:
            if to is None:
                to = frm
            if not (impl.FROM <= frm <= impl.TO):
                raise ValueError(f"Lower range 'frm={frm}' out of bounds.")
            if not (impl.FROM <= to <= impl.TO):
                raise ValueError(f"Upper range 'to={to}' out of bounds.")
            if frm >= to:
                raise ValueError("Unacceptable range.")

        # User values length validation
        if self.method == "user" and values is not None:
            if len(values) != 4:
                raise ValueError("Values must have 4 items.")

        # Store params for generate(); optional metadata for params dict
        self._frm = frm
        self._to = to
        self._values = values
        self._stdev = stdev
        self._corr = corr

        # Params for historical average / histochastic are populated in generate()
        # Params for stochastic (corr when user didn't provide) set in generate()

        if self.method == "stochastic":
            # Store correlation for later; if user didn't provide, we use identity
            # and will capture the actual matrix when we build covar in generate
            if corr is not None:
                corr_matrix = impl._build_corr_matrix(corr)
                self.params["corr"] = corr_matrix.copy()
            # else: identity is implicit; we'll set params["corr"] in generate when we have it

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
        method = self.method

        if method in FIXED_PRESET_METHODS:
            from owlplanner.rates import get_fixed_rates_decimal
            rates_decimal = get_fixed_rates_decimal(method)
            return impl.generate_fixed_series(N, rates_decimal)

        if method == "user":
            rates_decimal = np.array(self._values, dtype=float) / 100.0
            return impl.generate_fixed_series(N, rates_decimal)

        if method == "historical":
            return impl.generate_historical_series(N, self._frm, self._to)

        if method == "historical average":
            series, means, stdev_arr, corr_arr = impl.generate_historical_average_series(
                N, self._frm, self._to, self.logger
            )
            self.params["values"] = means.copy()
            self.params["stdev"] = stdev_arr.copy()
            self.params["corr"] = corr_arr.copy()
            return series

        if method == "histochastic":
            series, means, stdev_arr, corr_arr = impl.generate_histochastic_series(
                N, self._frm, self._to, self._rng, self.logger
            )
            self.params["values"] = means.copy()
            self.params["stdev"] = stdev_arr.copy()
            self.params["corr"] = corr_arr.copy()
            return series

        if method == "stochastic":
            series, means, stdev_arr, corr_matrix = impl.generate_stochastic_series(
                N,
                self._values,
                self._stdev,
                corr=self._corr,
                rng=self._rng,
            )
            self.params["corr"] = corr_matrix.copy()
            return series

        raise ValueError(f"Method '{method}' not implemented.")

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
