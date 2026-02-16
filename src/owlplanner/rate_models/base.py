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

    model_name = "base"
    description = "Abstract rate model."
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
        and optionally rejects unknown parameters.

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
        Must return array shape (N, 4)
        Columns:
        [S&P 500, Corporate Baa, T Bonds, Inflation]
        All values must be decimal.
        """
        pass

    #######################################################################
    # Model Properties
    #######################################################################

    @property
    def deterministic(self):
        return False

    @property
    def constant(self):
        return False

    #######################################################################
    # Metadata
    #######################################################################

    @classmethod
    def get_metadata(cls):
        return {
            "model_name": cls.model_name,
            "description": cls.description,
            "required_parameters": cls.required_parameters,
            "optional_parameters": cls.optional_parameters,
        }
