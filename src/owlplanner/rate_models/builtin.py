"""
Built-in rate models — one class per method.
All new rate models should subclass BaseRateModel.

Copyright (C) 2025-2026 The Owlplanner Authors
"""
###########################################################################
import numpy as np

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rate_models import _builtin_impl as impl


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _normalize_aliases(config: dict) -> dict:
    """Remap TOML names: standard_deviations→stdev, correlations→corr."""
    config = dict(config)
    if "standard_deviations" in config and "stdev" not in config:
        config["stdev"] = config.pop("standard_deviations")
    if "correlations" in config and "corr" not in config:
        config["corr"] = config.pop("correlations")
    return config


def _validate_historical_range(frm: int, to: int) -> None:
    if not (impl.FROM <= frm <= impl.TO):
        raise ValueError(f"Lower range 'frm={frm}' out of bounds.")
    if not (impl.FROM <= to <= impl.TO):
        raise ValueError(f"Upper range 'to={to}' out of bounds.")
    if frm >= to:
        raise ValueError("Unacceptable range.")


# ---------------------------------------------------------------------------
# Fixed-preset models
# ---------------------------------------------------------------------------

class DefaultRateModel(BaseRateModel):
    model_name = "default"
    description = "30-year trailing historical average deterministic rates."
    deterministic = True
    constant = True
    required_parameters = {}
    optional_parameters = {}

    def generate(self, N):
        from owlplanner.rates import get_fixed_rates_decimal
        return impl.generate_fixed_series(N, get_fixed_rates_decimal("default"))


class OptimisticRateModel(BaseRateModel):
    model_name = "optimistic"
    description = "Optimistic fixed rates based on industry forecasts."
    deterministic = True
    constant = True
    required_parameters = {}
    optional_parameters = {}

    def generate(self, N):
        from owlplanner.rates import get_fixed_rates_decimal
        return impl.generate_fixed_series(N, get_fixed_rates_decimal("optimistic"))


class ConservativeRateModel(BaseRateModel):
    model_name = "conservative"
    description = "Conservative fixed rate assumptions."
    deterministic = True
    constant = True
    required_parameters = {}
    optional_parameters = {}

    def generate(self, N):
        from owlplanner.rates import get_fixed_rates_decimal
        return impl.generate_fixed_series(N, get_fixed_rates_decimal("conservative"))


# ---------------------------------------------------------------------------
# User-specified fixed rates
# ---------------------------------------------------------------------------

class UserRateModel(BaseRateModel):
    model_name = "user"
    description = "User-specified fixed annual rates (percent)."
    deterministic = True
    constant = True
    required_parameters = {
        "values": {
            "type": "list[float]",
            "length": 4,
            "description": "Rates in percent: [S&P 500, Bonds Baa, T-Notes, Inflation]",
            "example": "[7.0, 4.5, 3.5, 2.5]",
        }
    }
    optional_parameters = {}

    def __init__(self, config, seed=None, logger=None):
        super().__init__(dict(config or {}), seed=seed, logger=logger)
        values = self.get_param("values")
        if values is not None and len(values) != 4:
            raise ValueError("Values must have 4 items.")
        self._values = values

    def generate(self, N):
        rates_decimal = np.array(self._values, dtype=float) / 100.0
        return impl.generate_fixed_series(N, rates_decimal)


# ---------------------------------------------------------------------------
# Historical deterministic models
# ---------------------------------------------------------------------------

class HistoricalRateModel(BaseRateModel):
    model_name = "historical"
    description = "Historical year-by-year returns over selected range."
    deterministic = True
    constant = False
    required_parameters = {
        "frm": {
            "type": "int",
            "description": "Starting historical year (inclusive).",
            "example": "1969",
        },
    }
    optional_parameters = {
        "to": {
            "type": "int",
            "description": (
                "Ending historical year (inclusive). "
                "Defaults to frm if not provided."
            ),
            "example": "2002",
        },
    }

    def __init__(self, config, seed=None, logger=None):
        super().__init__(dict(config or {}), seed=seed, logger=logger)
        frm = self.get_param("frm")
        to = self.get_param("to")
        if to is None:
            to = frm
        _validate_historical_range(frm, to)
        self._frm = frm
        self._to = to

    def generate(self, N):
        return impl.generate_historical_series(N, self._frm, self._to)


class HistoricalAverageRateModel(BaseRateModel):
    model_name = "historical average"
    description = "Fixed rates equal to historical average over selected range."
    deterministic = True
    constant = True
    required_parameters = {
        "frm": {
            "type": "int",
            "example": "1969",
        },
        "to": {
            "type": "int",
            "example": "2002",
        },
    }
    optional_parameters = {}

    def __init__(self, config, seed=None, logger=None):
        super().__init__(dict(config or {}), seed=seed, logger=logger)
        frm = self.get_param("frm")
        to = self.get_param("to")
        _validate_historical_range(frm, to)
        self._frm = frm
        self._to = to

    def generate(self, N):
        series, means, stdev_arr, corr_arr = impl.generate_historical_average_series(
            N, self._frm, self._to, self.logger
        )
        self.params["values"] = means.copy()
        self.params["stdev"] = stdev_arr.copy()
        self.params["corr"] = corr_arr.copy()
        return series


# ---------------------------------------------------------------------------
# Stochastic models
# ---------------------------------------------------------------------------

class StochasticRateModel(BaseRateModel):
    model_name = "stochastic"
    description = "Multivariate normal stochastic model using user-provided mean and volatility."
    deterministic = False
    constant = False
    required_parameters = {
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
    }
    optional_parameters = {
        "corr": {
            "type": "4x4 matrix or list[6]",
            "description": (
                "Pearson correlation coefficient (-1 to 1). "
                "Matrix or upper-triangle off-diagonals. Standard in finance/statistics."
            ),
            "example": "[0.2, 0.1, 0.0, 0.3, 0.1, 0.2]",
        }
    }

    def __init__(self, config, seed=None, logger=None):
        config = _normalize_aliases(dict(config or {}))
        rate_seed = config.pop("rate_seed", seed)
        super().__init__(config, seed=seed, logger=logger)
        self._rng = np.random.default_rng(rate_seed)
        self._values = self.get_param("values")
        self._stdev = self.get_param("stdev")
        self._corr = self.get_param("corr")
        if self._corr is not None:
            corr_matrix = impl._build_corr_matrix(self._corr)
            self.params["corr"] = corr_matrix.copy()

    def generate(self, N):
        series, means, stdev_arr, corr_matrix = impl.generate_stochastic_series(
            N,
            self._values,
            self._stdev,
            corr=self._corr,
            rng=self._rng,
        )
        self.params["corr"] = corr_matrix.copy()
        return series


class HistochasticRateModel(BaseRateModel):
    model_name = "histochastic"
    description = "Multivariate normal model using historical mean and covariance."
    deterministic = False
    constant = False
    required_parameters = {
        "frm": {
            "type": "int",
            "example": "1969",
        },
        "to": {
            "type": "int",
            "example": "2002",
        },
    }
    optional_parameters = {}

    def __init__(self, config, seed=None, logger=None):
        config = _normalize_aliases(dict(config or {}))
        rate_seed = config.pop("rate_seed", seed)
        super().__init__(config, seed=seed, logger=logger)
        self._rng = np.random.default_rng(rate_seed)
        frm = self.get_param("frm")
        to = self.get_param("to")
        _validate_historical_range(frm, to)
        self._frm = frm
        self._to = to

    def generate(self, N):
        series, means, stdev_arr, corr_arr = impl.generate_histochastic_series(
            N, self._frm, self._to, self._rng, self.logger
        )
        self.params["values"] = means.copy()
        self.params["stdev"] = stdev_arr.copy()
        self.params["corr"] = corr_arr.copy()
        return series


# ---------------------------------------------------------------------------
# Registry and backward-compatibility shim
# ---------------------------------------------------------------------------

_BUILTIN_REGISTRY = {
    "default": DefaultRateModel,
    "optimistic": OptimisticRateModel,
    "conservative": ConservativeRateModel,
    "user": UserRateModel,
    "historical": HistoricalRateModel,
    "historical average": HistoricalAverageRateModel,
    "stochastic": StochasticRateModel,
    "histochastic": HistochasticRateModel,
}


class BuiltinRateModel:
    """Backward-compatibility shim — delegates to the appropriate concrete class."""

    @staticmethod
    def list_methods():
        return set(_BUILTIN_REGISTRY.keys())

    def __new__(cls, config, seed=None, logger=None):
        config = dict(config or {})
        method = config.get("method")
        if method not in _BUILTIN_REGISTRY:
            raise ValueError(f"Unknown builtin rate method '{method}'.")
        return _BUILTIN_REGISTRY[method](config, seed=seed, logger=logger)
