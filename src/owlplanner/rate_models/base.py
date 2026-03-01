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
from typing import Any, Optional
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
    more_info: Optional[str] = None

    # Model characteristics
    deterministic = False
    constant = False

    # Parameter schema
    required_parameters: dict[str, Any] = {}
    optional_parameters: dict[str, Any] = {}

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
    # TOML Serialization Interface
    #######################################################################

    @classmethod
    def from_config(cls, rates_section: dict) -> dict:
        """
        Extract and normalize model-specific parameters from a rates_selection dict.

        Called by plan_bridge when loading a TOML config.  The default implementation:

        - Translates the TOML key ``from`` to the internal key ``frm``.
        - Coerces ``frm`` and ``to`` to int.
        - Filters the result to only the keys declared in ``required_parameters``
          and ``optional_parameters``.

        Subclasses with non-standard TOML formats (renamed keys, nested structures,
        type transformations) may override this method.

        Args:
            rates_section: The raw rates_selection dict from the config, with
                global keys (method, dividend_rate, etc.) already removed.

        Returns:
            A kwargs dict suitable for passing to ``plan.setRates(**kwargs)``.
        """
        section = dict(rates_section)
        # Translate TOML 'from' → internal 'frm' for backward compat.
        if "from" in section:
            section["frm"] = section.pop("from")
        if "frm" in section:
            section["frm"] = int(section["frm"])
        if "to" in section:
            section["to"] = int(section["to"])
        allowed = set(cls.required_parameters) | set(cls.optional_parameters)
        return {k: v for k, v in section.items() if k in allowed}

    @classmethod
    def to_config(cls, **params) -> dict:
        """
        Serialize model-specific parameters to a flat dict for TOML rates_selection.

        Called by plan_bridge when saving a Plan to config.  The default implementation:

        - Filters ``params`` to only the keys declared in ``required_parameters``
          and ``optional_parameters``.
        - Renames the internal key ``frm`` back to the TOML key ``from``.

        Subclasses with non-standard TOML formats (renamed keys, type transformations,
        derived fields) may override this method.

        Args:
            **params: The model's current parameter dict (e.g. ``plan.rateModel.params``).

        Returns:
            A dict of model-specific fields to merge into the rates_selection section.
        """
        allowed = set(cls.required_parameters) | set(cls.optional_parameters)
        result = {k: v for k, v in params.items() if k in allowed}
        # Translate internal 'frm' → TOML 'from' for backward compat.
        if "frm" in result:
            result["from"] = result.pop("frm")
        return result

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
