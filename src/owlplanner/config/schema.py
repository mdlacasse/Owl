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

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .defaults import DEFAULT_DOB, DEFAULT_LIFE_EXPECTANCY, DEFAULT_PENSION_AGE, DEFAULT_SS_AGE


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
    "aca_settings",
}


# Reserved section for user-defined keys (preserved on load/save)
USER_SECTION = "user"


class BasicInfo(BaseModel):
    """Basic information about individuals in the plan."""

    model_config = ConfigDict(extra="allow")

    status: str = Field(default="single", description="Filing status: single or married")
    names: List[str] = Field(
        default=[""],
        min_length=1,
        max_length=2,
        description="Individual names",
    )
    date_of_birth: Optional[List[str]] = None  # Default applied in bridge
    life_expectancy: List[int] = Field(default=[89], description="Life expectancy in years")
    sexes: Optional[List[str]] = Field(default=None, description="Biological sex per individual: 'M' or 'F'")
    start_date: Optional[str] = Field(default="today", description="Plan start date")


class SavingsAssets(BaseModel):
    """Initial account balances and beneficiary information."""

    model_config = ConfigDict(extra="allow")

    taxable_savings_balances: List[float] = Field(
        default=[0.0], description="Taxable account balances ($k)"
    )
    tax_deferred_savings_balances: List[float] = Field(
        default=[0.0], description="Tax-deferred balances ($k)"
    )
    tax_free_savings_balances: List[float] = Field(
        default=[0.0], description="Tax-free balances ($k)"
    )
    hsa_savings_balances: List[float] = Field(
        default=[0.0], description="HSA balances ($k)"
    )
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
    pension_ages: List[float] = Field(default=[65.0], description="Age at pension start")
    pension_indexed: List[bool] = Field(default=[True], description="Whether pension is inflation-indexed")
    pension_survivor_fraction: Optional[List[float]] = Field(
        default=None,
        description="Fraction of pension (0-1) continuing to surviving spouse. 0 = single-life.",
    )
    social_security_pia_amounts: Optional[List[int]] = None
    social_security_ages: List[float] = Field(default=[67.0], description="Age at SS start (FRA)")
    social_security_trim_pct: Optional[int] = Field(
        default=0, description="% reduction in SS benefits from trim_year onward"
    )
    social_security_trim_year: Optional[int] = Field(
        default=None, description="Year when SS benefit reduction begins"
    )
    spia_individuals: List[int] = Field(
        default_factory=list,
        description="Individual index (0 = first, 1 = second) for each SPIA entry.",
    )
    spia_buy_years: List[int] = Field(
        default_factory=list,
        description=("Calendar year of SPIA purchase for each entry."
                     " Use a year before plan start for already-purchased annuities (no premium deducted)."),
    )
    spia_premiums: List[float] = Field(
        default_factory=list,
        description=("Lump-sum purchase price in dollars for each SPIA."
                     " Deducted from the tax-deferred account in the buy year as a non-taxable IRA rollover."
                     " Set to 0 for annuities purchased before the plan start."),
    )
    spia_monthly_incomes: List[float] = Field(
        default_factory=list,
        description="Monthly income in today's dollars for each SPIA. Payments are fully taxable as ordinary income.",
    )
    spia_indexed: List[bool] = Field(
        default_factory=list,
        description="Whether each SPIA is CPI-indexed (True) or pays a fixed nominal amount (False).",
    )
    spia_survivor_fractions: List[float] = Field(
        default_factory=list,
        description=("Fraction of income (0–1) continuing to the surviving spouse after the annuitant's death."
                     " 0 = single-life; 0.5, 0.75, or 1.0 = joint-and-survivor. Ignored for single individuals."),
    )


class RatesSelection(BaseModel):
    """Investment return rates and inflation assumptions."""

    model_config = ConfigDict(extra="allow")

    heirs_rate_on_tax_deferred_estate: float = Field(default=30.0, description="Heirs tax rate (%)")
    effective_tax_rate: float = Field(
        default=20.0,
        description="Effective tax rate on tax-deferred assets for spending-to-savings ratio (%)")
    dividend_rate: Optional[float] = Field(default=1.8, description="Dividend rate (%)")
    obbba_expiration_year: Optional[int] = Field(default=2032, description="OBBBA expiry year")
    method: str = Field(default="historical average", description="Rate method")
    # Conditional fields (present based on method)
    from_: Optional[int] = Field(default=None, alias="from", description="Historical start year")
    to: Optional[int] = Field(default=None, description="Historical end year")
    values: Optional[List[float]] = None  # user, gaussian, lognormal
    standard_deviations: Optional[List[float]] = None  # gaussian, lognormal
    correlations: Optional[List[float]] = None  # gaussian, lognormal
    rate_seed: Optional[int] = None  # gaussian, histogaussian, lognormal, histolognormal
    reproducible_rates: Optional[bool] = Field(
        default=False, description="Reproducible stochastic (gaussian, histogaussian, etc.)"
    )
    reverse_sequence: Optional[bool] = Field(default=False, description="Reverse rate sequence")
    roll_sequence: Optional[int] = Field(default=0, description="Roll rate sequence")
    bootstrap_type: Optional[str] = Field(default=None, description="Bootstrap type for bootstrap_sor")
    block_size: Optional[int] = Field(default=None, description="Block size for block-based bootstraps")
    shrink: Optional[bool] = Field(default=None, description="Spectral shrinkage for VAR(1)")


class AssetAllocation(BaseModel):
    """Asset allocation strategy."""

    model_config = ConfigDict(extra="allow")

    interpolation_method: Literal["linear", "s-curve"] = Field(
        default="s-curve", description="linear or s-curve"
    )
    interpolation_center: Optional[float] = Field(
        default=None, description="Interpolation center (years); required for s-curve"
    )
    interpolation_width: Optional[float] = Field(
        default=None, description="Interpolation width (years); required for s-curve"
    )
    type: str = Field(default="individual", description="account, individual, or spouses")
    # Conditional: generic for individual/spouses, taxable/tax-deferred/tax-free for account
    generic: Optional[List[List[List[int]]]] = None
    taxable: Optional[List[List[List[int]]]] = None
    tax_deferred: Optional[List[List[List[int]]]] = Field(default=None, alias="tax-deferred")
    tax_free: Optional[List[List[List[int]]]] = Field(default=None, alias="tax-free")

    @field_validator("interpolation_method", mode="before")
    @classmethod
    def _normalize_interpolation_method(cls, v: Any) -> Any:
        if isinstance(v, str):
            s = v.strip().lower()
            if s not in ("linear", "s-curve"):
                raise ValueError("interpolation_method must be 'linear' or 's-curve'")
            return s
        return v

    @model_validator(mode="after")
    def _s_curve_requires_center_width(self) -> "AssetAllocation":
        if self.interpolation_method == "s-curve":
            if self.interpolation_center is None or self.interpolation_width is None:
                raise ValueError(
                    "interpolation_center and interpolation_width are required when "
                    "interpolation_method is 's-curve'"
                )
        return self


class OptimizationParameters(BaseModel):
    """Optimization objective and spending profile."""

    model_config = ConfigDict(extra="allow")

    spending_profile: str = Field(default="smile", description="flat or smile")
    surviving_spouse_spending_percent: int = Field(default=60, description="Survivor %")
    objective: str = Field(default="maxSpending", description="maxSpending, maxBequest, or maxHybrid")
    smile_dip: Optional[int] = Field(default=15, description="Smile profile dip %")
    smile_increase: Optional[int] = Field(default=12, description="Smile profile increase %")
    smile_delay: Optional[int] = Field(default=0, description="Smile profile delay years")


class ACASettings(BaseModel):
    """ACA marketplace health insurance configuration."""

    model_config = ConfigDict(extra="allow")

    slcsp_annual: float = Field(
        default=0.0,
        description="Annual benchmark Silver plan (SLCSP) premium in today's dollars ($k)",
    )
    aca_start_year: int = Field(
        default=0,
        description="Calendar year ACA coverage begins (0 = from plan start).",
    )


class Results(BaseModel):
    """Result display parameters."""

    model_config = ConfigDict(extra="allow")

    default_plots: str = Field(default="nominal", description="nominal or today")
    worksheet_show_ages: bool = Field(
        default=False,
        description="Show per-person age columns (Dec 31) in Streamlit Worksheets tables",
    )
    worksheet_hide_zero_columns: bool = Field(
        default=False,
        description="Hide numeric columns that are all zero in Streamlit Worksheets tables",
    )
    worksheet_real_dollars: bool = Field(
        default=False,
        description="Display and save worksheet values in real (inflation-adjusted) dollars",
    )


class SolverOptions(BaseModel):
    """
    Solver options for the optimization routine.

    Single source of truth for option names, types, and validation.
    Accepts both camelCase (internal/TOML) and snake_case (CLI via alias).
    Unknown keys are preserved (extra='allow') for forward compatibility.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Core solver selection and limits
    solver: Optional[Literal["default", "HiGHS", "MOSEK"]] = None
    maxTime: Optional[float] = Field(default=None, alias="max_time",
                                     description="Per-iteration solver time limit (seconds). Default 900.")
    gap: Optional[float] = None
    verbose: Optional[bool] = None

    # Tolerances
    absTol: Optional[float] = None
    relTol: Optional[float] = None
    epsilon: Optional[float] = None

    # Iteration limits
    maxIter: Optional[int] = None
    bendersMaxIter: Optional[int] = None

    # Roth conversion options (float or "file")
    maxRothConversion: Optional[Union[float, str]] = None
    noRothConversions: Optional[str] = None

    startRothConversions: Optional[int] = None
    swapRothConverters: Optional[int] = None

    @field_validator("maxRothConversion", mode="before")
    @classmethod
    def _coerce_max_roth(cls, v: Any) -> Any:
        if v is None or v == "file":
            return v
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.strip():
            try:
                return float(v)
            except ValueError:
                return v  # e.g. "file" stays as str
        return v

    # Objectives and constraints
    bequest: Optional[float] = None
    netSpending: Optional[float] = None
    spendingWeight: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Blend weight for maxHybrid: 1=maximize spending, 0=maximize bequest."
    )
    spendingFloor: Optional[float] = Field(
        default=None,
        description="Minimum annual net spending (today's $k) for maxHybrid objective."
    )
    timePreference: Optional[float] = Field(
        default=None, ge=0.0,
        description="Subjective time discount rate (%/year). Values >0 front-load spending "
                    "by valuing near-term consumption more than end-of-life spending."
    )
    minTaxableBalance: Optional[List[float]] = None
    spendingSlack: Optional[int] = None
    noLateSurplus: Optional[bool] = None

    # AMO / Big-M
    amoConstraints: Optional[bool] = None
    amoRoth: Optional[bool] = None
    amoSurplus: Optional[bool] = None
    bigMamo: Optional[float] = None
    bigMaca: Optional[float] = None
    bigMss: Optional[float] = None
    bigMltcg: Optional[float] = None
    bigMniit: Optional[float] = None

    # Medicare, ACA, LTCG, NIIT, SS taxability
    withMedicare: Optional[Union[str, bool]] = None
    includeMedicarePartD: Optional[bool] = None
    medicarePartDBasePremium: Optional[float] = None
    withACA: Optional[str] = None
    withLTCG: Optional[str] = None
    withNIIT: Optional[str] = None
    withSSTaxability: Optional[Union[str, float]] = None
    withDecomposition: Optional[str] = None
    withSCLoop: Optional[bool] = None

    # Other
    previousMAGIs: Optional[List[float]] = None
    oppCostX: Optional[float] = None
    units: Optional[str] = None


def parse_solver_options(raw: dict) -> dict:
    """
    Validate and coerce solver options through the schema.

    Single source of truth for parsing: used by TOML load, plan_bridge, and CLI.
    Returns a dict suitable for plan.solverOptions.
    """
    if not raw:
        return {}
    validated = SolverOptions.model_validate(raw)
    # Exclude None to avoid overwriting plan defaults
    dumped = validated.model_dump(by_alias=False, exclude_none=True)
    # model_dump includes extras when extra='allow'; merge model_extra if present
    extras = getattr(validated, "model_extra", None)
    if extras:
        dumped.update(extras)
    return dumped


# Map CLI flag names (snake_case) to schema field names (camelCase)
CLI_SOLVER_OVERRIDE_MAP = {
    "max_time": "maxTime",
    "max-time": "maxTime",
}


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
    aca_settings: Optional[ACASettings] = None

    @model_validator(mode="after")
    def _align_lists_to_household_size(self) -> "CaseConfig":
        """
        Pad per-person lists to len(basic_info.names) so Pydantic defaults like
        ``hsa_savings_balances = [0.0]`` do not break married cases when a key
        is omitted from TOML (matches plan_bridge ``[0.0] * icount`` behavior).
        """
        ni = len(self.basic_info.names)
        if ni < 1 or ni > 2:
            raise ValueError(f"basic_info.names must have 1 or 2 entries, got {ni}")

        bi = self.basic_info
        new_bi = bi.model_copy(
            update={
                "life_expectancy": _pad_int_list(
                    list(bi.life_expectancy), ni, field="life_expectancy",
                    fill_from_tail=True,
                ),
                "date_of_birth": _pad_optional_str_list(bi.date_of_birth, ni, field="date_of_birth"),
                "sexes": _pad_optional_sexes(bi.sexes, ni),
            }
        )

        sa = self.savings_assets
        new_sa = sa.model_copy(
            update={
                "taxable_savings_balances": _pad_float_list(
                    sa.taxable_savings_balances, ni, field="taxable_savings_balances", fill=0.0,
                ),
                "tax_deferred_savings_balances": _pad_float_list(
                    sa.tax_deferred_savings_balances, ni, field="tax_deferred_savings_balances", fill=0.0,
                ),
                "tax_free_savings_balances": _pad_float_list(
                    sa.tax_free_savings_balances, ni, field="tax_free_savings_balances", fill=0.0,
                ),
                "hsa_savings_balances": _pad_float_list(
                    sa.hsa_savings_balances, ni, field="hsa_savings_balances", fill=0.0,
                ),
            }
        )
        benf = sa.beneficiary_fractions
        if benf is not None and ni == 2 and len(benf) == 3:
            new_sa = new_sa.model_copy(update={"beneficiary_fractions": list(benf) + [1.0]})

        fi = self.fixed_income
        p_monthly = fi.pension_monthly_amounts
        if p_monthly is not None:
            p_monthly = _pad_float_list(list(p_monthly), ni, field="pension_monthly_amounts", fill=0.0)
        p_surv = fi.pension_survivor_fraction
        if p_surv is not None:
            p_surv = _pad_float_list(list(p_surv), ni, field="pension_survivor_fraction", fill=0.0)
        ss_pia = fi.social_security_pia_amounts
        if ss_pia is not None:
            ss_pia = _pad_int_list(list(ss_pia), ni, field="social_security_pia_amounts", fill=0)

        new_fi = fi.model_copy(
            update={
                "pension_monthly_amounts": p_monthly,
                "pension_ages": _pad_float_list(
                    list(fi.pension_ages), ni, field="pension_ages", fill=DEFAULT_PENSION_AGE,
                ),
                "pension_indexed": _pad_bool_list(list(fi.pension_indexed), ni, field="pension_indexed"),
                "pension_survivor_fraction": p_surv,
                "social_security_pia_amounts": ss_pia,
                "social_security_ages": _pad_float_list(
                    list(fi.social_security_ages), ni, field="social_security_ages", fill=DEFAULT_SS_AGE,
                ),
            }
        )

        return self.model_copy(
            update={"basic_info": new_bi, "savings_assets": new_sa, "fixed_income": new_fi}
        )


def _list_too_long(field: str, ni: int, n: int) -> None:
    if n > ni:
        raise ValueError(f"{field} must have at most {ni} entries (household size), got {n}")


def _pad_float_list(vals: List[float], ni: int, *, field: str, fill: float) -> List[float]:
    _list_too_long(field, ni, len(vals))
    if len(vals) < ni:
        return list(vals) + [fill] * (ni - len(vals))
    return list(vals)


def _pad_int_list(
    vals: List[int], ni: int, *, field: str, fill: int | None = None, fill_from_tail: bool = False,
) -> List[int]:
    _list_too_long(field, ni, len(vals))
    if len(vals) < ni:
        tail = vals[-1] if fill_from_tail and vals else (fill if fill is not None else DEFAULT_LIFE_EXPECTANCY)
        return list(vals) + [tail] * (ni - len(vals))
    return list(vals)


def _pad_bool_list(vals: List[bool], ni: int, *, field: str) -> List[bool]:
    _list_too_long(field, ni, len(vals))
    if len(vals) < ni:
        fill = vals[-1] if vals else True
        return list(vals) + [fill] * (ni - len(vals))
    return list(vals)


def _pad_optional_str_list(vals: Optional[List[str]], ni: int, *, field: str) -> Optional[List[str]]:
    if vals is None:
        return None
    _list_too_long(field, ni, len(vals))
    if len(vals) < ni:
        return list(vals) + [DEFAULT_DOB] * (ni - len(vals))
    return list(vals)


def _pad_optional_sexes(vals: Optional[List[str]], ni: int) -> Optional[List[str]]:
    if vals is None:
        return None
    _list_too_long("sexes", ni, len(vals))
    if len(vals) < ni:
        defaults = ["M", "F"] if ni == 2 else ["F"]
        return list(vals) + [defaults[i] for i in range(len(vals), ni)]
    return list(vals)


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
