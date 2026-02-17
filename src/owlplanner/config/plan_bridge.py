"""
Bridge between configuration dict and Plan object.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import os
from datetime import date
from typing import TYPE_CHECKING, Any

import numpy as np

from owlplanner import mylogging as log
from owlplanner.rates import FROM, TO
from owlplanner.rate_models.loader import load_rate_model

from .schema import KNOWN_SECTIONS

if TYPE_CHECKING:
    from owlplanner.plan import Plan

AccountTypes = ["taxable", "tax-deferred", "tax-free"]

account_key_map = {
    "taxable": "taxable_savings_balances",
    "tax-deferred": "tax_deferred_savings_balances",
    "tax-free": "tax_free_savings_balances",
}


def _extract_extra(diconf: dict) -> dict:
    """Extract unknown top-level sections for round-trip preservation."""
    return {k: v for k, v in diconf.items() if k not in KNOWN_SECTIONS}


def _get_known(diconf: dict) -> dict:
    """Get only known sections (for plan building)."""
    return {k: v for k, v in diconf.items() if k in KNOWN_SECTIONS}


def config_to_plan(
    diconf: dict,
    dirname: str = "",
    *,
    verbose: bool = True,
    logstreams=None,
    loadHFP: bool = True,
) -> "Plan":
    """
    Build a Plan from a configuration dict.

    Unknown top-level sections in diconf are stored in plan._config_extra for
    round-trip when saving.

    Args:
        diconf: Full configuration dict (from load_toml)
        dirname: Directory of config file (for resolving HFP relative paths)
        verbose: Logger verbosity
        logstreams: Logger streams
        loadHFP: Whether to load the Household Financial Profile file
    """
    from owlplanner import plan

    mylog = log.Logger(verbose, logstreams)

    # Preserve unknown sections for round-trip
    extra = _extract_extra(diconf)
    known = _get_known(diconf)

    # Basic Info
    name = known["case_name"]
    inames = known["basic_info"]["names"]
    icount = len(inames)
    dobs = known["basic_info"].get("date_of_birth", ["1965-01-15"] * icount)
    expectancy = known["basic_info"]["life_expectancy"]
    s = ["", "s"][icount - 1]
    mylog.vprint(f"Plan for {icount} individual{s}: {inames}.")
    p = plan.Plan(inames, dobs, expectancy, name, verbose=True, logstreams=logstreams)
    p._description = known.get("description", "")
    p._config_extra = extra

    # Assets: config/TOML in $k (per PARAMETERS.md); plan uses dollars. Copy lists to avoid mutation.
    start_date = known["basic_info"].get("start_date", "today")
    balances = {}
    for acc in AccountTypes:
        balances[acc] = list(known["savings_assets"][account_key_map[acc]])
    p.setAccountBalances(
        taxable=balances["taxable"],
        taxDeferred=balances["tax-deferred"],
        taxFree=balances["tax-free"],
        startDate=start_date,
    )
    if icount == 2:
        phi_j = known["savings_assets"]["beneficiary_fractions"]
        p.setBeneficiaryFractions(phi_j)
        eta = known["savings_assets"]["spousal_surplus_deposit_fraction"]
        p.setSpousalDepositFraction(eta)

    # Household Financial Profile
    hfp_section = known.get("household_financial_profile", {})
    time_lists_file = hfp_section.get("HFP_file_name", "None")
    if time_lists_file != "None":
        if loadHFP:
            if os.path.exists(time_lists_file):
                myfile = time_lists_file
            elif dirname and os.path.exists(os.path.join(dirname, time_lists_file)):
                myfile = os.path.join(dirname, time_lists_file)
            else:
                raise FileNotFoundError(f"File '{time_lists_file}' not found.")
            p.readHFP(myfile)
        else:
            p.timeListsFileName = time_lists_file
            mylog.vprint(f"Ignoring HFP file {time_lists_file}.")

    # Fixed Income
    ssec_amounts = np.array(
        known["fixed_income"].get("social_security_pia_amounts", [0] * icount),
        dtype=np.int32,
    )
    ssec_ages = np.array(known["fixed_income"]["social_security_ages"])
    p.setSocialSecurity(ssec_amounts, ssec_ages)
    pension_amounts = np.array(
        known["fixed_income"].get("pension_monthly_amounts", [0] * icount),
        dtype=np.float32,
    )
    pension_ages = np.array(known["fixed_income"]["pension_ages"])
    pension_indexed = known["fixed_income"]["pension_indexed"]
    p.setPension(pension_amounts, pension_ages, pension_indexed)

    # --------------------------------------------------
    # Rates Selection (metadata-driven)
    # --------------------------------------------------

    rates_section = dict(known["rates_selection"])

    # Required base fields handled outside setRates
    p.setDividendRate(float(rates_section.get("dividend_rate", 1.8)))
    p.setHeirsTaxRate(float(rates_section["heirs_rate_on_tax_deferred_estate"]))
    p.yOBBBA = int(rates_section.get("obbba_expiration_year", 2032))

    rate_method = rates_section.pop("method")
    # Remove Plan-level keys so they are not passed to RateModel
    rates_section.pop("dividend_rate", None)
    rates_section.pop("heirs_rate_on_tax_deferred_estate", None)
    rates_section.pop("obbba_expiration_year", None)


    # Handle reproducibility separately (Plan-level state)
    rate_seed = rates_section.pop("rate_seed", None)
    reproducible_rates = rates_section.pop("reproducible_rates", False)

    if rate_seed is not None:
        rate_seed = int(rate_seed)

    if reproducible_rates or rate_seed is not None:
        p.setReproducible(bool(reproducible_rates), seed=rate_seed)

    # Extract transform flags (Plan-level)
    reverse = bool(rates_section.pop("reverse_sequence", False))
    roll = int(rates_section.pop("roll_sequence", 0))

    # Rename config keys if needed for internal consistency
    # (UI uses "from", internal uses "frm")
    if "from" in rates_section:
        rates_section["frm"] = rates_section.pop("from")

    if "frm" in rates_section:
        rates_section["frm"] = int(rates_section["frm"])

    if "to" in rates_section:
        rates_section["to"] = int(rates_section["to"])

    # Legacy compatibility: auto-fill to for historical methods if missing
    if rate_method in ("historical", "historical average", "histochastic"):
        if "frm" not in rates_section:
            raise ValueError(
                f"Rate method '{rate_method}' requires 'from' year."
            )

        # Auto-fill to if missing (legacy behavior)
        if "to" not in rates_section:
            rates_section["to"] = int(rates_section["frm"]) + p.N_n - 1
        
    # Clean parameters prior to call to setRates

    ModelClass = load_rate_model(rate_method)

    # Metadata filtering
    ModelClass = load_rate_model(rate_method)

    if ModelClass.model_name == "builtin":
        # Builtin model has per-method metadata
        metadata = ModelClass.get_method_metadata(rate_method)
    else:
        metadata = ModelClass.get_metadata()

    required = set(metadata.get("required_parameters", {}).keys())
    optional = set(metadata.get("optional_parameters", {}).keys())
    allowed = required | optional

    clean_rate_section = {
        k: v for k, v in rates_section.items() if k in allowed
    }

    # Call metadata-driven setRates
    p.setRates(
        method=rate_method,
        reverse=reverse,
        roll=roll,
        **clean_rate_section,
    )

    # Asset Allocation
    p.setInterpolationMethod(
        known["asset_allocation"]["interpolation_method"],
        float(known["asset_allocation"]["interpolation_center"]),
        float(known["asset_allocation"]["interpolation_width"]),
    )
    alloc_type = known["asset_allocation"]["type"]
    if alloc_type == "account":
        bounds_ar = {}
        for a_type in AccountTypes:
            bounds_ar[a_type] = np.array(
                known["asset_allocation"][a_type],
                dtype=np.float64,
            )
        p.setAllocationRatios(
            alloc_type,
            taxable=bounds_ar["taxable"],
            taxDeferred=bounds_ar["tax-deferred"],
            taxFree=bounds_ar["tax-free"],
        )
    elif alloc_type in ["individual", "spouses"]:
        bounds_generic = np.array(
            known["asset_allocation"]["generic"],
            dtype=np.float64,
        )
        p.setAllocationRatios(alloc_type, generic=bounds_generic)
    else:
        raise ValueError(f"Unknown asset allocation type {alloc_type}.")

    # Optimization Parameters
    p.objective = known["optimization_parameters"]["objective"]
    profile = known["optimization_parameters"]["spending_profile"]
    survivor = int(known["optimization_parameters"]["surviving_spouse_spending_percent"])
    if profile == "smile":
        dip = int(known["optimization_parameters"]["smile_dip"])
        increase = int(known["optimization_parameters"]["smile_increase"])
        delay = int(known["optimization_parameters"]["smile_delay"])
    else:
        dip = 15
        increase = 12
        delay = 0
    p.setSpendingProfile(profile, survivor, dip, increase, delay)

    # Solver Options
    p.solverOptions = dict(known["solver_options"])
    if "withMedicare" not in p.solverOptions:
        p.solverOptions["withMedicare"] = "loop"
    if "withSCLoop" not in p.solverOptions:
        p.solverOptions["withSCLoop"] = True
    with_medicare = p.solverOptions.get("withMedicare")
    if isinstance(with_medicare, bool):
        p.solverOptions["withMedicare"] = "loop" if with_medicare else "None"
    name_opt = p.solverOptions.get("noRothConversions", "None")
    if name_opt != "None" and name_opt not in p.inames:
        raise ValueError(f"Unknown name {name_opt} for noRothConversions.")
    this_year = date.today().year
    year = p.solverOptions.get("startRothConversions", this_year)
    p.solverOptions["startRothConversions"] = max(year, this_year)
    p.yOBBBA = max(p.yOBBBA, this_year)

    # Results
    p.setDefaultPlots(known["results"]["default_plots"])

    return p


def apply_config_to_plan(plan: "Plan", diconf: dict) -> None:
    """
    Apply configuration dict to an existing Plan.

    Used by the UI before solving: sync UI state (via ui_to_config) to the plan.
    Assumes plan already exists with correct N_i; only updates configurable fields.
    """
    known = _get_known(diconf)
    icount = plan.N_i

    # Basic info (description, start_date only - names/dobs/life require new plan)
    plan._description = known.get("description", "")
    start_date = known["basic_info"].get("start_date", "today")

    # Assets: config/TOML in $k (per PARAMETERS.md); plan uses dollars. Copy lists to avoid mutation.
    balances = {}
    for acc in AccountTypes:
        balances[acc] = list(known["savings_assets"][account_key_map[acc]])
    plan.setAccountBalances(
        taxable=balances["taxable"],
        taxDeferred=balances["tax-deferred"],
        taxFree=balances["tax-free"],
        startDate=start_date,
    )
    if icount == 2:
        phi_j = known["savings_assets"]["beneficiary_fractions"]
        plan.setBeneficiaryFractions(phi_j)
        eta = known["savings_assets"]["spousal_surplus_deposit_fraction"]
        plan.setSpousalDepositFraction(eta)

    # Fixed Income
    ssec_amounts = np.array(
        known["fixed_income"].get("social_security_pia_amounts", [0] * icount),
        dtype=np.int32,
    )
    ssec_ages = np.array(known["fixed_income"]["social_security_ages"])
    plan.setSocialSecurity(ssec_amounts, ssec_ages)
    pension_amounts = np.array(
        known["fixed_income"].get("pension_monthly_amounts", [0] * icount),
        dtype=np.float32,
    )
    pension_ages = np.array(known["fixed_income"]["pension_ages"])
    pension_indexed = known["fixed_income"]["pension_indexed"]
    plan.setPension(pension_amounts, pension_ages, pension_indexed)

    # --------------------------------------------------
    # Rates Selection (metadata-driven)
    # --------------------------------------------------

    rates_section = dict(known["rates_selection"])

    # Plan-level rate settings
    plan.setDividendRate(float(rates_section.get("dividend_rate", 1.8)))
    plan.setHeirsTaxRate(float(rates_section["heirs_rate_on_tax_deferred_estate"]))
    plan.yOBBBA = int(rates_section.get("obbba_expiration_year", 2032))

    # Remove plan-level keys
    rates_section.pop("dividend_rate", None)
    rates_section.pop("heirs_rate_on_tax_deferred_estate", None)
    rates_section.pop("obbba_expiration_year", None)

    rate_method = rates_section.pop("method")

    # Reproducibility
    rate_seed = rates_section.pop("rate_seed", None)
    reproducible_rates = rates_section.pop("reproducible_rates", False)

    if rate_seed is not None:
        rate_seed = int(rate_seed)

    if reproducible_rates or rate_seed is not None:
        plan.setReproducible(bool(reproducible_rates), seed=rate_seed)

    # Transform flags
    reverse = bool(rates_section.pop("reverse_sequence", False))
    roll = int(rates_section.pop("roll_sequence", 0))

    # Normalize naming
    if "from" in rates_section:
        rates_section["frm"] = rates_section.pop("from")

    if "frm" in rates_section:
        rates_section["frm"] = int(rates_section["frm"])

    if "to" in rates_section:
        rates_section["to"] = int(rates_section["to"])

    # Legacy auto-fill for historical
    if rate_method in ("historical", "historical average", "histochastic"):
        if "frm" not in rates_section:
            raise ValueError(
                f"Rate method '{rate_method}' requires 'from' year."
            )

        if "to" not in rates_section:
            rates_section["to"] = int(rates_section["frm"]) + plan.N_n - 1

    ModelClass = load_rate_model(rate_method)

    # Metadata filtering
    ModelClass = load_rate_model(rate_method)

    if ModelClass.model_name == "builtin":
        # Builtin model has per-method metadata
        metadata = ModelClass.get_method_metadata(rate_method)
    else:
        metadata = ModelClass.get_metadata()

    required = set(metadata.get("required_parameters", {}).keys())
    optional = set(metadata.get("optional_parameters", {}).keys())
    allowed = required | optional

    clean_rate_section = {
        k: v for k, v in rates_section.items() if k in allowed
    }

    plan.setRates(
        method=rate_method,
        reverse=reverse,
        roll=roll,
        **clean_rate_section,
    )

    # Asset Allocation
    plan.setInterpolationMethod(
        known["asset_allocation"]["interpolation_method"],
        float(known["asset_allocation"]["interpolation_center"]),
        float(known["asset_allocation"]["interpolation_width"]),
    )
    alloc_type = known["asset_allocation"]["type"]
    if alloc_type == "account":
        bounds_ar = {}
        for a_type in AccountTypes:
            bounds_ar[a_type] = np.array(
                known["asset_allocation"][a_type],
                dtype=np.float64,
            )
        plan.setAllocationRatios(
            alloc_type,
            taxable=bounds_ar["taxable"],
            taxDeferred=bounds_ar["tax-deferred"],
            taxFree=bounds_ar["tax-free"],
        )
    elif alloc_type in ["individual", "spouses"]:
        bounds_generic = np.array(
            known["asset_allocation"]["generic"],
            dtype=np.float64,
        )
        plan.setAllocationRatios(alloc_type, generic=bounds_generic)

    # Optimization Parameters
    plan.objective = known["optimization_parameters"]["objective"]
    profile = known["optimization_parameters"]["spending_profile"]
    survivor = int(known["optimization_parameters"]["surviving_spouse_spending_percent"])
    if profile == "smile":
        dip = int(known["optimization_parameters"].get("smile_dip", 15))
        increase = int(known["optimization_parameters"].get("smile_increase", 12))
        delay = int(known["optimization_parameters"].get("smile_delay", 0))
    else:
        dip = 15
        increase = 12
        delay = 0
    plan.setSpendingProfile(profile, survivor, dip, increase, delay)

    # Solver Options
    plan.solverOptions = dict(known.get("solver_options", {}))
    name_opt = plan.solverOptions.get("noRothConversions", "None")
    if name_opt != "None" and name_opt not in plan.inames:
        raise ValueError(f"Unknown name {name_opt} for noRothConversions.")
    if "withMedicare" not in plan.solverOptions:
        plan.solverOptions["withMedicare"] = "loop"
    if "withSCLoop" not in plan.solverOptions:
        plan.solverOptions["withSCLoop"] = True
    with_medicare = plan.solverOptions.get("withMedicare")
    if isinstance(with_medicare, bool):
        plan.solverOptions["withMedicare"] = "loop" if with_medicare else "None"
    this_year = date.today().year
    year = plan.solverOptions.get("startRothConversions", this_year)
    plan.solverOptions["startRothConversions"] = max(year, this_year)
    plan.yOBBBA = max(plan.yOBBBA, this_year)

    # Results
    plan.setDefaultPlots(known.get("results", {}).get("default_plots", "nominal"))


def plan_to_config(myplan: "Plan") -> dict:
    """
    Build a configuration dict from a Plan.

    Merges plan._config_extra (if present) for round-trip of user-defined keys.
    """
    diconf: dict[str, Any] = {}
    diconf["case_name"] = myplan._name
    diconf["description"] = myplan._description

    # Basic Info
    diconf["basic_info"] = {
        "status": ["unknown", "single", "married"][myplan.N_i],
        "names": myplan.inames,
        "date_of_birth": myplan.dobs,
        "life_expectancy": myplan.expectancy.tolist(),
        "start_date": myplan.startDate,
    }

    # Savings Assets
    diconf["savings_assets"] = {}
    for j in range(myplan.N_j):
        amounts = myplan.beta_ij[:, j] / 1000  # plan dollars -> config $k
        diconf["savings_assets"][account_key_map[AccountTypes[j]]] = amounts.tolist()
    if myplan.N_i == 2:
        diconf["savings_assets"]["beneficiary_fractions"] = myplan.phi_j.tolist()
        diconf["savings_assets"]["spousal_surplus_deposit_fraction"] = myplan.eta

    # Household Financial Profile
    diconf["household_financial_profile"] = {
        "HFP_file_name": myplan.timeListsFileName,
    }

    # Fixed Income
    diconf["fixed_income"] = {
        "pension_monthly_amounts": myplan.pensionAmounts.tolist(),
        "pension_ages": myplan.pensionAges.tolist(),
        "pension_indexed": myplan.pensionIsIndexed,
        "social_security_pia_amounts": myplan.ssecAmounts.tolist(),
        "social_security_ages": myplan.ssecAges.tolist(),
    }

    # Rates Selection
    diconf["rates_selection"] = {
        "heirs_rate_on_tax_deferred_estate": float(100 * myplan.nu),
        "dividend_rate": float(100 * myplan.mu),
        "obbba_expiration_year": myplan.yOBBBA,
        "method": myplan.rateMethod,
    }
    if myplan.rateMethod in ["stochastic", "histochastic"]:
        if myplan.rateSeed is not None:
            diconf["rates_selection"]["rate_seed"] = int(myplan.rateSeed)
        diconf["rates_selection"]["reproducible_rates"] = bool(myplan.reproducibleRates)
    if myplan.rateMethod in ["user", "stochastic"]:
        # Plan stores rateValues in percent (API/config format), not decimal.
        diconf["rates_selection"]["values"] = myplan.rateValues.tolist()
    if myplan.rateMethod == "stochastic":
        # Plan stores rateStdev in percent; rateCorr as coefficient (-1 to 1).
        diconf["rates_selection"]["standard_deviations"] = myplan.rateStdev.tolist()
        # Correlations: extract upper triangle as coefficient (-1 to 1).
        corr_upper = []
        for k1 in range(myplan.N_k):
            for k2 in range(k1 + 1, myplan.N_k):
                corr_upper.append(float(myplan.rateCorr[k1, k2]))
        diconf["rates_selection"]["correlations"] = corr_upper
    if myplan.rateMethod in ["historical average", "historical", "histochastic"]:
        diconf["rates_selection"]["from"] = int(myplan.rateFrm)
        diconf["rates_selection"]["to"] = int(myplan.rateTo)
    else:
        diconf["rates_selection"]["from"] = int(FROM)
        diconf["rates_selection"]["to"] = int(TO)
    diconf["rates_selection"]["reverse_sequence"] = bool(myplan.rateReverse)
    diconf["rates_selection"]["roll_sequence"] = int(myplan.rateRoll)

    # Asset Allocation
    diconf["asset_allocation"] = {
        "interpolation_method": myplan.interpMethod,
        "interpolation_center": float(myplan.interpCenter),
        "interpolation_width": float(myplan.interpWidth),
        "type": myplan.ARCoord,
    }
    if myplan.ARCoord == "account":
        for acc_type in AccountTypes:
            val = myplan.boundsAR[acc_type]
            diconf["asset_allocation"][acc_type] = (
                val.tolist() if hasattr(val, "tolist") else val
            )
    else:
        val = myplan.boundsAR["generic"]
        diconf["asset_allocation"]["generic"] = (
            val.tolist() if hasattr(val, "tolist") else val
        )

    # Optimization Parameters
    diconf["optimization_parameters"] = {
        "spending_profile": myplan.spendingProfile,
        "surviving_spouse_spending_percent": int(100 * myplan.chi),
        "objective": myplan.objective,
    }
    if myplan.spendingProfile == "smile":
        diconf["optimization_parameters"]["smile_dip"] = int(myplan.smileDip)
        diconf["optimization_parameters"]["smile_increase"] = int(myplan.smileIncrease)
        diconf["optimization_parameters"]["smile_delay"] = int(myplan.smileDelay)

    diconf["solver_options"] = dict(myplan.solverOptions)
    diconf["results"] = {"default_plots": myplan.defaultPlots}

    # Merge user-defined sections for round-trip
    extra = getattr(myplan, "_config_extra", None)
    if extra:
        for key, value in extra.items():
            diconf[key] = value

    return diconf
