"""
Shared constants for rate models.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

# Required column names for DataFrame rate input (order: Stocks, Bonds, Fixed, Inflation).
REQUIRED_RATE_COLUMNS = ("S&P 500", "Bonds Baa", "TNotes", "Inflation")

# Built-in method name sets. Must stay in sync with BuiltinRateModel.BUILTINS_METADATA.

# Methods using canonical fixed preset rates (default, optimistic, conservative).
FIXED_PRESET_METHODS = ("default", "optimistic", "conservative")

# Methods that produce same rate every year; reverse/roll are no-ops.
CONSTANT_RATE_METHODS = (
    "default", "optimistic", "conservative", "user", "historical average"
)

# Methods that produce deterministic series; no regeneration needed.
RATE_METHODS_NO_REGEN = (
    "default", "optimistic", "conservative", "user",
    "historical average", "historical",
)

# Methods requiring frm/to year range.
HISTORICAL_RANGE_METHODS = ("historical", "historical average", "histochastic")

# Methods using stochastic generation; need seed, support regenRates.
STOCHASTIC_METHODS = ("stochastic", "histochastic")

# Methods that store user-provided values (for plan_to_config).
METHODS_WITH_VALUES = ("user", "stochastic")

# Methods the UI treats as "fixed" type (vs varying).
FIXED_TYPE_UI = ("default", "conservative", "optimistic", "historical average", "user")

# Methods the UI treats as "varying" type.
VARYING_TYPE_UI = ("historical", "histochastic", "stochastic")
