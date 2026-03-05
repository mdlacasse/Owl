"""
Shared default values and default_config() factory for Owl case configuration.

Provides a single source of truth for defaults used when building cases from
scratch (e.g. in the UI) so they align with TOML-loaded cases.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from __future__ import annotations

import copy
from datetime import date

from owlplanner.rates import get_fixed_rate_values


# Default constants (aligned with SSA/actuarial conventions)
DEFAULT_LIFE_EXPECTANCY = 89
DEFAULT_SS_AGE = 67.0  # Full retirement age for many birth years
DEFAULT_PENSION_AGE = 65.0
DEFAULT_DOB = "1965-01-15"
DEFAULT_HEIRS_RATE = 30.0
DEFAULT_DIVIDEND_RATE = 1.8
DEFAULT_OBBBA_YEAR = 2032
# Default allocation: 60/40 stock/bond initially, 70/30 at end (per individual)
DEFAULT_GENERIC_ALLOCATION = [[[60, 40, 0, 0], [70, 30, 0, 0]]]


def default_config(ni: int = 1) -> dict:
    """
    Return a minimal valid configuration dict for a scratch-built case.

    Use this when creating a new case from scratch (e.g. in the UI) to ensure
    all required config keys are present with sensible defaults, independent
    of which pages the user has visited.

    Args:
        ni: Number of individuals (1 for single, 2 for married).

    Returns:
        Configuration dict suitable for config_to_ui() or config_to_plan().
    """
    if ni not in (1, 2):
        raise ValueError(f"ni must be 1 or 2, got {ni}")

    this_year = date.today().year

    diconf = {
        "case_name": "",
        "description": "",
        "basic_info": {
            "status": "single" if ni == 1 else "married",
            "names": [""] * ni,
            "date_of_birth": [DEFAULT_DOB] * ni,
            "life_expectancy": [DEFAULT_LIFE_EXPECTANCY] * ni,
            "start_date": "today",
        },
        "savings_assets": {
            "taxable_savings_balances": [0.0] * ni,
            "tax_deferred_savings_balances": [0.0] * ni,
            "tax_free_savings_balances": [0.0] * ni,
        },
        "household_financial_profile": {
            "HFP_file_name": "None",
        },
        "fixed_income": {
            "pension_monthly_amounts": [0.0] * ni,
            "pension_ages": [DEFAULT_PENSION_AGE] * ni,
            "pension_indexed": [True] * ni,
            "social_security_pia_amounts": [0] * ni,
            "social_security_ages": [DEFAULT_SS_AGE] * ni,
            "social_security_trim_pct": 0,
            "social_security_trim_year": None,
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": DEFAULT_HEIRS_RATE,
            "dividend_rate": DEFAULT_DIVIDEND_RATE,
            "obbba_expiration_year": DEFAULT_OBBBA_YEAR,
            "method": "historical average",
            "from": 1969,
            "to": this_year - 1,
            "values": get_fixed_rate_values("conservative"),
            "reverse_sequence": False,
            "roll_sequence": 0,
        },
        "asset_allocation": {
            "interpolation_method": "s-curve",
            "interpolation_center": 15.0,
            "interpolation_width": 5.0,
            "type": "individual",
            "generic": [
                copy.deepcopy(DEFAULT_GENERIC_ALLOCATION[0]) for _ in range(ni)
            ],
        },
        "optimization_parameters": {
            "spending_profile": "smile",
            "surviving_spouse_spending_percent": 60,
            "objective": "maxSpending",
            "smile_dip": 15,
            "smile_increase": 12,
            "smile_delay": 0,
        },
        "solver_options": {},
        "results": {"default_plots": "nominal"},
    }

    if ni == 2:
        diconf["savings_assets"]["beneficiary_fractions"] = [1.0, 1.0, 1.0]
        diconf["savings_assets"]["spousal_surplus_deposit_fraction"] = 0.5

    return diconf
