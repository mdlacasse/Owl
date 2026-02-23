"""
Pydantic schema for Owl case configuration.

Defines the canonical structure for TOML case files. Unknown keys are preserved
in model_extra for round-trip of user-defined data.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# Known top-level section names (used for extracting unknown keys)
KNOWN_SECTIONS = {
    "case_name",
    "description",
    "basic_info",
    "savings_assets",
    "household_financial_profile",
    "fixed_income",
    "rates_selection",
    "asset_allocation",
    "optimization_parameters",
    "solver_options",
    "results",
}


# Reserved section for user-defined keys (preserved on load/save)
USER_SECTION = "user"


class BasicInfo(BaseModel):
    """Basic information about individuals in the plan."""

    model_config = ConfigDict(extra="allow")

    status: str = Field(description="Filing status: single or married")
    names: List[str] = Field(min_length=1, max_length=2, description="Individual names")
    date_of_birth: Optional[List[str]] = None  # Default applied in bridge
    life_expectancy: List[int] = Field(description="Life expectancy in years")
    start_date: Optional[str] = Field(default="today", description="Plan start date")


class SavingsAssets(BaseModel):
    """Initial account balances and beneficiary information."""

    model_config = ConfigDict(extra="allow")

    taxable_savings_balances: List[float] = Field(description="Taxable account balances ($k)")
    tax_deferred_savings_balances: List[float] = Field(description="Tax-deferred balances ($k)")
    tax_free_savings_balances: List[float] = Field(description="Tax-free balances ($k)")
    beneficiary_fractions: Optional[List[float]] = None  # Married only
    spousal_surplus_deposit_fraction: Optional[float] = None  # Married only


class HouseholdFinancialProfile(BaseModel):
    """Reference to Excel file with wages and contributions."""

    model_config = ConfigDict(extra="allow")

    HFP_file_name: str = Field(default="None", description="Excel filename or None")


class FixedIncome(BaseModel):
    """Pension and Social Security information."""

    model_config = ConfigDict(extra="allow")

    pension_monthly_amounts: Optional[List[float]] = None
    pension_ages: List[float] = Field(description="Age at pension start")
    pension_indexed: List[bool] = Field(description="Whether pension is inflation-indexed")
    social_security_pia_amounts: Optional[List[int]] = None
    social_security_ages: List[float] = Field(description="Age at SS start")
    social_security_trim_pct: Optional[int] = Field(
        default=0, description="% reduction in SS benefits from trim_year onward"
    )
    social_security_trim_year: Optional[int] = Field(
        default=None, description="Year when SS benefit reduction begins"
    )
    social_security_tax_fraction: Optional[float] = Field(
        default=None,
        description=(
            "Fixed SS taxability fraction in [0, 1]. Overrides the self-consistent-loop "
            "computation. Use 0.0 (PI < $32k MFJ/$25k single), 0.5 (mid-range PI), or "
            "0.85 (high PI, default when absent). Omit to use dynamic computation."
        ),
    )


class RatesSelection(BaseModel):
    """Investment return rates and inflation assumptions."""

    model_config = ConfigDict(extra="allow")

    heirs_rate_on_tax_deferred_estate: float = Field(description="Heirs tax rate (%)")
    dividend_rate: Optional[float] = Field(default=1.8, description="Dividend rate (%)")
    obbba_expiration_year: Optional[int] = Field(default=2032, description="OBBBA expiry year")
    method: str = Field(description="Rate method")
    # Conditional fields (present based on method)
    from_: Optional[int] = Field(default=None, alias="from", description="Historical start year")
    to: Optional[int] = Field(default=None, description="Historical end year")
    values: Optional[List[float]] = None  # user, stochastic
    standard_deviations: Optional[List[float]] = None  # stochastic
    correlations: Optional[List[float]] = None  # stochastic
    rate_seed: Optional[int] = None  # stochastic, histochastic
    reproducible_rates: Optional[bool] = Field(default=False, description="Reproducible stochastic")
    reverse_sequence: Optional[bool] = Field(default=False, description="Reverse rate sequence")
    roll_sequence: Optional[int] = Field(default=0, description="Roll rate sequence")


class AssetAllocation(BaseModel):
    """Asset allocation strategy."""

    model_config = ConfigDict(extra="allow")

    interpolation_method: str = Field(description="linear or s-curve")
    interpolation_center: float = Field(description="Interpolation center (years)")
    interpolation_width: float = Field(description="Interpolation width (years)")
    type: str = Field(description="account, individual, or spouses")
    # Conditional: generic for individual/spouses, taxable/tax-deferred/tax-free for account
    generic: Optional[List[List[List[int]]]] = None
    taxable: Optional[List[List[List[int]]]] = None
    tax_deferred: Optional[List[List[List[int]]]] = Field(default=None, alias="tax-deferred")
    tax_free: Optional[List[List[List[int]]]] = Field(default=None, alias="tax-free")


class OptimizationParameters(BaseModel):
    """Optimization objective and spending profile."""

    model_config = ConfigDict(extra="allow")

    spending_profile: str = Field(description="flat or smile")
    surviving_spouse_spending_percent: int = Field(default=60, description="Survivor %")
    objective: str = Field(description="maxSpending or maxBequest")
    smile_dip: Optional[int] = Field(default=15, description="Smile profile dip %")
    smile_increase: Optional[int] = Field(default=12, description="Smile profile increase %")
    smile_delay: Optional[int] = Field(default=0, description="Smile profile delay years")


class Results(BaseModel):
    """Result display parameters."""

    model_config = ConfigDict(extra="allow")

    default_plots: str = Field(default="nominal", description="nominal or today")


class CaseConfig(BaseModel):
    """
    Root configuration schema for an Owl case.

    Unknown top-level sections (e.g. [user], [custom]) are preserved in
    model_extra and round-tripped on save.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    case_name: str = Field(default="", description="Case/plan name")
    description: str = Field(default="", description="Case description")
    basic_info: BasicInfo
    savings_assets: SavingsAssets
    household_financial_profile: HouseholdFinancialProfile
    fixed_income: FixedIncome
    rates_selection: RatesSelection
    asset_allocation: AssetAllocation
    optimization_parameters: OptimizationParameters
    solver_options: Dict[str, Any] = Field(default_factory=dict)
    results: Results


def config_dict_to_model(diconf: dict) -> tuple[CaseConfig, dict]:
    """
    Convert a configuration dict to a validated CaseConfig and extract unknown keys.

    Returns:
        (CaseConfig, extra_dict): validated config and dict of unknown top-level sections
    """
    extra: dict = {}
    known: dict = {}

    for key, value in diconf.items():
        if key in KNOWN_SECTIONS:
            known[key] = value
        else:
            extra[key] = value

    config = CaseConfig.model_validate(known)
    return config, extra


def model_to_config_dict(config: CaseConfig, extra: dict | None = None) -> dict:
    """
    Convert CaseConfig (and optional extra dict) back to a flat config dict for TOML output.
    """
    out = config.model_dump(by_alias=True, exclude_none=False)
    # Ensure we have proper structure for solver_options
    if "solver_options" not in out:
        out["solver_options"] = {}
    if extra:
        for key, value in extra.items():
            out[key] = value
    return out
