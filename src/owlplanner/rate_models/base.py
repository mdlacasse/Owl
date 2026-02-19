"""
Base class for future rate models.

Centralizes:
- Required parameter validation
- Optional parameter defaults
- Unknown parameter checking
- Metadata exposure

All rate models must subclass this.

Copyright (C) 2025-2026 The Owlplanner Authors
"""
###########################################################################
from abc import ABC, abstractmethod
import numpy as np


class BaseRateModel(ABC):
    """
    All rate models must subclass this.
    """

    # ------------------------------------------------------------
    # Core Metadata (Class-Level)
    # ------------------------------------------------------------

    model_name = "base"
    description = "Abstract rate model."
    more_info = None

    # Model characteristics
    deterministic = False
    constant = False

    # Parameter schema
    required_parameters = {}
    optional_parameters = {}

    #######################################################################
    # Initialization
    #######################################################################

    def __init__(self, config, seed=None, logger=None, **kwargs):
        self.config = config or {}
        self.seed = seed
        self.logger = logger

        # Normalize and validate parameters
        self.params = self._validate_and_normalize_parameters(self.config)

    #######################################################################
    # Parameter Validation (Centralized)
    #######################################################################

    def _validate_and_normalize_parameters(self, config):
        """
        Validates required parameters, applies optional defaults,
        and rejects unknown parameters.

        Returns:
            normalized parameter dictionary
        """

        required = self.required_parameters or {}
        optional = self.optional_parameters or {}

        normalized = {}

        # --------------------------------------------------
        # 1. Validate required parameters
        # --------------------------------------------------
        for param in required:
            if config.get(param) is None:
                raise ValueError(
                    f"Rate model '{self.model_name}' "
                    f"requires parameter '{param}'."
                )
            normalized[param] = config[param]

        # --------------------------------------------------
        # 2. Apply optional parameters with defaults
        # --------------------------------------------------
        for param, meta in optional.items():
            if param in config and config[param] is not None:
                normalized[param] = config[param]
            else:
                if "default" in meta:
                    normalized[param] = meta["default"]

        # --------------------------------------------------
        # 3. Detect unknown parameters
        # --------------------------------------------------
        allowed = set(required.keys()) | set(optional.keys()) | {"method"}

        for key in config:
            if key not in allowed:
                raise ValueError(
                    f"Unknown parameter '{key}' for rate model "
                    f"'{self.model_name}'."
                )

        return normalized

    #######################################################################
    # Parameter Access Helper
    #######################################################################

    def get_param(self, name, default=None):
        """
        Safe parameter accessor.
        """
        return self.params.get(name, default)

    #######################################################################
    # Required Interface
    #######################################################################

    @abstractmethod
    def generate(self, N) -> np.ndarray:
        """
        Generate an (N, 4) rate series in **decimal** format.

        Columns: [S&P 500, Bonds Baa, T-Notes, Inflation]

        Plugin convention
        -----------------
        - Return values must be decimal (e.g. 0.07 = 7%).  Internal callers
          transpose the result into plan.tau_kn which is always decimal.
        - If your plugin accepts user-facing parameters such as ``values`` or
          ``stdev``, accept them in **percent** (e.g. 7.0 = 7%) for consistency
          with setRates() and getRatesDistributions().
        - Correlation / covariance matrices are always in **decimal** (−1 to 1).
        """
        pass

    #######################################################################
    # Metadata Exposure
    #######################################################################

    @classmethod
    def get_metadata(cls):
        """
        Returns normalized metadata dictionary for documentation
        and model discovery.
        """
        return {
            "model_name": getattr(cls, "model_name", None),
            "description": getattr(cls, "description", ""),
            "more_info": getattr(cls, "more_info", None),
            "required_parameters": getattr(cls, "required_parameters", {}),
            "optional_parameters": getattr(cls, "optional_parameters", {}),
            "deterministic": getattr(cls, "deterministic", False),
            "constant": getattr(cls, "constant", False),
        }
