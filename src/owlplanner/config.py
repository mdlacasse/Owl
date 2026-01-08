"""
Configuration management for saving and loading case parameters.

This module provides utility functions to save and load retirement planning
case parameters in TOML format.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import toml
from io import StringIO, BytesIO
import numpy as np
from datetime import date
import os

from owlplanner import plan
from owlplanner import mylogging as log
from owlplanner.rates import FROM, TO


AccountTypes = ["taxable", "tax-deferred", "tax-free"]


# Translation dictionary for backward compatibility: old keys -> new snake_case keys
_KEY_TRANSLATION = {
    # Root level keys
    "Plan Name": "case_name",
    "Description": "description",
    # Section names
    "Basic Info": "basic_info",
    "Assets": "savings_assets",
    "Household Financial Profile": "household_financial_profile",
    "Fixed Income": "fixed_income",
    "Rates Selection": "rates_selection",
    "Asset Allocation": "asset_allocation",
    "Optimization Parameters": "optimization_parameters",
    "Solver Options": "solver_options",
    "Results": "results",
    # Basic Info keys
    "Status": "status",
    "Names": "names",
    "Date of birth": "date_of_birth",
    "Life expectancy": "life_expectancy",
    "Start date": "start_date",
    # Assets keys
    "taxable savings balances": "taxable_savings_balances",
    "tax-deferred savings balances": "tax_deferred_savings_balances",
    "tax-free savings balances": "tax_free_savings_balances",
    "Beneficiary fractions": "beneficiary_fractions",
    "Spousal surplus deposit fraction": "spousal_surplus_deposit_fraction",
    # Household Financial Profile keys
    "HFP file name": "HFP_file_name",
    # Fixed Income keys
    "Pension monthly amounts": "pension_monthly_amounts",
    "Pension ages": "pension_ages",
    "Pension indexed": "pension_indexed",
    "Social security PIA amounts": "social_security_pia_amounts",
    "Social security ages": "social_security_ages",
    # Rates Selection keys
    "Heirs rate on tax-deferred estate": "heirs_rate_on_tax_deferred_estate",
    "Dividend rate": "dividend_rate",
    "OBBBA expiration year": "obbba_expiration_year",
    "Method": "method",
    "Rate seed": "rate_seed",
    "Reproducible rates": "reproducible_rates",
    "Values": "values",
    "Standard deviations": "standard_deviations",
    "Correlations": "correlations",
    "From": "from",
    "To": "to",
    # Asset Allocation keys
    "Interpolation method": "interpolation_method",
    "Interpolation center": "interpolation_center",
    "Interpolation width": "interpolation_width",
    "Type": "type",
    # Optimization Parameters keys
    "Spending profile": "spending_profile",
    "Surviving spouse spending percent": "surviving_spouse_spending_percent",
    "Smile dip": "smile_dip",
    "Smile increase": "smile_increase",
    "Smile delay": "smile_delay",
    "Objective": "objective",
    # Results keys
    "Default plots": "default_plots",
}


def translate_old_keys(diconf):
    """
    Translate old TOML keys to new snake_case keys for backward compatibility.
    This function recursively processes the configuration dictionary and replaces
    old keys with new snake_case keys.

    Args:
        diconf: Configuration dictionary (may be modified in place)

    Returns:
        Dictionary with translated keys
    """
    if not isinstance(diconf, dict):
        return diconf

    translated = {}

    # First, translate section names at the top level
    for key, value in diconf.items():
        new_key = _KEY_TRANSLATION.get(key, key)

        if isinstance(value, dict):
            # Recursively translate keys within sections
            translated[new_key] = {}
            for sub_key, sub_value in value.items():
                new_sub_key = _KEY_TRANSLATION.get(sub_key, sub_key)
                if isinstance(sub_value, dict):
                    translated[new_key][new_sub_key] = translate_old_keys(sub_value)
                else:
                    translated[new_key][new_sub_key] = sub_value
        else:
            translated[new_key] = value

    return translated


def saveConfig(myplan, file, mylog):
    """
    Save case parameters and return a dictionary containing all parameters.
    """

    diconf = {}
    diconf["case_name"] = myplan._name
    diconf["description"] = myplan._description

    # Basic Info.
    diconf["basic_info"] = {
        "status": ["unknown", "single", "married"][myplan.N_i],
        "names": myplan.inames,
        "date_of_birth": myplan.dobs,
        "life_expectancy": myplan.expectancy.tolist(),
        "start_date": myplan.startDate,
    }

    # Assets.
    diconf["savings_assets"] = {}
    for j in range(myplan.N_j):
        amounts = myplan.beta_ij[:, j] / 1000
        # Map account type names to snake_case keys
        account_key_map = {
            "taxable": "taxable_savings_balances",
            "tax-deferred": "tax_deferred_savings_balances",
            "tax-free": "tax_free_savings_balances"
        }
        diconf["savings_assets"][account_key_map[AccountTypes[j]]] = amounts.tolist()
    if myplan.N_i == 2:
        diconf["savings_assets"]["beneficiary_fractions"] = myplan.phi_j.tolist()
        diconf["savings_assets"]["spousal_surplus_deposit_fraction"] = myplan.eta

    # Household Financial Profile
    diconf["household_financial_profile"] = {"HFP_file_name": myplan.timeListsFileName}

    # Fixed Income.
    diconf["fixed_income"] = {
        "pension_monthly_amounts": (myplan.pensionAmounts).tolist(),
        "pension_ages": myplan.pensionAges.tolist(),
        "pension_indexed": myplan.pensionIsIndexed,
        "social_security_pia_amounts": (myplan.ssecAmounts).tolist(),
        "social_security_ages": myplan.ssecAges.tolist(),
    }

    # Rates Selection.
    diconf["rates_selection"] = {
        "heirs_rate_on_tax_deferred_estate": float(100 * myplan.nu),
        "dividend_rate": float(100 * myplan.mu),
        "obbba_expiration_year": myplan.yOBBBA,
        "method": myplan.rateMethod,
    }
    # Store seed and reproducibility flag for stochastic methods
    if myplan.rateMethod in ["stochastic", "histochastic"]:
        if myplan.rateSeed is not None:
            diconf["rates_selection"]["rate_seed"] = int(myplan.rateSeed)
        diconf["rates_selection"]["reproducible_rates"] = bool(myplan.reproducibleRates)
    if myplan.rateMethod in ["user", "stochastic"]:
        diconf["rates_selection"]["values"] = (100 * myplan.rateValues).tolist()
    if myplan.rateMethod in ["stochastic"]:
        diconf["rates_selection"]["standard_deviations"] = (100 * myplan.rateStdev).tolist()
        diconf["rates_selection"]["correlations"] = myplan.rateCorr.tolist()
    if myplan.rateMethod in ["historical average", "historical", "histochastic"]:
        diconf["rates_selection"]["from"] = int(myplan.rateFrm)
        diconf["rates_selection"]["to"] = int(myplan.rateTo)
    else:
        diconf["rates_selection"]["from"] = int(FROM)
        diconf["rates_selection"]["to"] = int(TO)

    # Asset Allocation.
    diconf["asset_allocation"] = {
        "interpolation_method": myplan.interpMethod,
        "interpolation_center": float(myplan.interpCenter),
        "interpolation_width": float(myplan.interpWidth),
        "type": myplan.ARCoord,
    }
    if myplan.ARCoord == "account":
        for accType in AccountTypes:
            diconf["asset_allocation"][accType] = myplan.boundsAR[accType]
    else:
        diconf["asset_allocation"]["generic"] = myplan.boundsAR["generic"]

    # Optimization Parameters.
    diconf["optimization_parameters"] = {
        "spending_profile": myplan.spendingProfile,
        "surviving_spouse_spending_percent": int(100 * myplan.chi),
    }
    if myplan.spendingProfile == "smile":
        diconf["optimization_parameters"]["smile_dip"] = int(myplan.smileDip)
        diconf["optimization_parameters"]["smile_increase"] = int(myplan.smileIncrease)
        diconf["optimization_parameters"]["smile_delay"] = int(myplan.smileDelay)

    diconf["optimization_parameters"]["objective"] = myplan.objective
    diconf["solver_options"] = myplan.solverOptions

    # Results.
    diconf["results"] = {"default_plots": myplan.defaultPlots}

    if isinstance(file, str):
        filename = file
        if not file.endswith(".toml"):
            filename = filename + ".toml"
        if not filename.startswith("case_"):
            filename = "case_" + filename
        mylog.vprint(f"Saving plan case file as '{filename}'.")

        try:
            with open(filename, "w") as casefile:
                toml.dump(diconf, casefile, encoder=toml.TomlNumpyEncoder())
        except Exception as e:
            raise RuntimeError(f"Failed to save case file {filename}: {e}") from e
    elif isinstance(file, StringIO):
        try:
            string = toml.dumps(diconf, encoder=toml.TomlNumpyEncoder())
            file.write(string)
        except Exception as e:
            raise RuntimeError(f"Failed to save case to StringIO: {e}") from e
    elif file is None:
        pass
    else:
        raise ValueError(f"Argument {type(file)} has unknown type")

    return diconf


def readConfig(file, *, verbose=True, logstreams=None, readContributions=True):
    """
    Read plan parameters from case file *basename*.toml.
    A new plan is created and returned.
    Argument file can be a filename, a file, or a stringIO.
    """
    mylog = log.Logger(verbose, logstreams)

    dirname = ""
    if isinstance(file, str):
        filename = file
        dirname = os.path.dirname(filename)
        if not filename.endswith(".toml"):
            filename = filename + ".toml"

        mylog.vprint(f"Reading plan from case file '{filename}'.")

        try:
            with open(filename, "r") as f:
                diconf = toml.load(f)
        except Exception as e:
            raise FileNotFoundError(f"File {filename} not found: {e}") from e
    elif isinstance(file, BytesIO):
        try:
            string = file.getvalue().decode("utf-8")
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError(f"Cannot read from BytesIO: {e}") from e
    elif isinstance(file, StringIO):
        try:
            string = file.getvalue()
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError(f"Cannot read from StringIO: {e}") from e
    else:
        raise ValueError(f"Type {type(file)} not a valid type")

    # Translate old keys to new snake_case keys for backward compatibility
    diconf = translate_old_keys(diconf)

    # Basic Info.
    name = diconf["case_name"]
    inames = diconf["basic_info"]["names"]
    icount = len(inames)
    # Default to January 15, 1965 if no entry is found.
    dobs = diconf["basic_info"].get("date_of_birth", ["1965-01-15"]*icount)
    expectancy = diconf["basic_info"]["life_expectancy"]
    s = ["", "s"][icount - 1]
    mylog.vprint(f"Plan for {icount} individual{s}: {inames}.")
    p = plan.Plan(inames, dobs, expectancy, name, verbose=True, logstreams=logstreams)
    p._description = diconf.get("description", "")

    # Assets.
    startDate = diconf["basic_info"].get("start_date", "today")
    balances = {}
    # Map account type names to snake_case keys
    account_key_map = {
        "taxable": "taxable_savings_balances",
        "tax-deferred": "tax_deferred_savings_balances",
        "tax-free": "tax_free_savings_balances"
    }
    for acc in AccountTypes:
        balances[acc] = diconf["savings_assets"][account_key_map[acc]]
    p.setAccountBalances(taxable=balances["taxable"], taxDeferred=balances["tax-deferred"],
                         taxFree=balances["tax-free"], startDate=startDate)
    if icount == 2:
        phi_j = diconf["savings_assets"]["beneficiary_fractions"]
        p.setBeneficiaryFractions(phi_j)
        eta = diconf["savings_assets"]["spousal_surplus_deposit_fraction"]
        p.setSpousalDepositFraction(eta)

    # Household Financial Profile
    hfp_section = diconf.get("household_financial_profile", {})
    timeListsFileName = hfp_section.get("HFP_file_name", "None")
    if timeListsFileName != "None":
        if readContributions:
            if os.path.exists(timeListsFileName):
                myfile = timeListsFileName
            elif dirname != "" and os.path.exists(os.path.join(dirname, timeListsFileName)):
                myfile = os.path.join(dirname, timeListsFileName)
            else:
                raise FileNotFoundError(f"File '{timeListsFileName}' not found.")
            p.readContributions(myfile)
        else:
            p.timeListsFileName = timeListsFileName
            mylog.vprint(f"Ignoring to read contributions file {timeListsFileName}.")

    # Fixed Income.
    ssecAmounts = np.array(diconf["fixed_income"].get("social_security_pia_amounts", [0]*icount), dtype=np.int32)
    ssecAges = np.array(diconf["fixed_income"]["social_security_ages"])
    p.setSocialSecurity(ssecAmounts, ssecAges)
    pensionAmounts = np.array(diconf["fixed_income"].get("pension_monthly_amounts", [0]*icount), dtype=np.float32)
    pensionAges = np.array(diconf["fixed_income"]["pension_ages"])
    pensionIsIndexed = diconf["fixed_income"]["pension_indexed"]
    p.setPension(pensionAmounts, pensionAges, pensionIsIndexed)

    # Rates Selection.
    p.setDividendRate(float(diconf["rates_selection"].get("dividend_rate", 1.8)))    # Fix for mod.
    p.setHeirsTaxRate(float(diconf["rates_selection"]["heirs_rate_on_tax_deferred_estate"]))
    p.yOBBBA = int(diconf["rates_selection"].get("obbba_expiration_year", 2032))

    frm = None
    to = None
    rateValues = None
    stdev = None
    rateCorr = None
    rateSeed = None
    reproducibleRates = False
    rateMethod = diconf["rates_selection"]["method"]
    if rateMethod in ["historical average", "historical", "histochastic"]:
        frm = diconf["rates_selection"]["from"]
        if not isinstance(frm, int):
            frm = int(frm)
        to = diconf["rates_selection"]["to"]
        if not isinstance(to, int):
            to = int(to)
    if rateMethod in ["user", "stochastic"]:
        rateValues = np.array(diconf["rates_selection"]["values"], dtype=np.float32)
    if rateMethod in ["stochastic"]:
        stdev = np.array(diconf["rates_selection"]["standard_deviations"], dtype=np.float32)
        rateCorr = np.array(diconf["rates_selection"]["correlations"], dtype=np.float32)
    # Load seed and reproducibility flag for stochastic methods
    if rateMethod in ["stochastic", "histochastic"]:
        rateSeed = diconf["rates_selection"].get("rate_seed")
        if rateSeed is not None:
            rateSeed = int(rateSeed)
        reproducibleRates = diconf["rates_selection"].get("reproducible_rates", False)
        p.setReproducible(reproducibleRates, seed=rateSeed)
    p.setRates(rateMethod, frm, to, rateValues, stdev, rateCorr)

    # Asset Allocation.
    boundsAR = {}
    p.setInterpolationMethod(
        diconf["asset_allocation"]["interpolation_method"],
        float(diconf["asset_allocation"]["interpolation_center"]),
        float(diconf["asset_allocation"]["interpolation_width"]),
    )
    allocType = diconf["asset_allocation"]["type"]
    if allocType == "account":
        for aType in AccountTypes:
            boundsAR[aType] = np.array(diconf["asset_allocation"][aType], dtype=np.float32)

        p.setAllocationRatios(
            allocType,
            taxable=boundsAR["taxable"],
            taxDeferred=boundsAR["tax-deferred"],
            taxFree=boundsAR["tax-free"],
        )
    elif allocType == "individual" or allocType == "spouses":
        boundsAR["generic"] = np.array(diconf["asset_allocation"]["generic"], dtype=np.float32)
        p.setAllocationRatios(
            allocType,
            generic=boundsAR["generic"],
        )
    else:
        raise ValueError(f"Unknown asset allocation type {allocType}.")

    # Optimization Parameters.
    p.objective = diconf["optimization_parameters"]["objective"]

    profile = diconf["optimization_parameters"]["spending_profile"]
    survivor = int(diconf["optimization_parameters"]["surviving_spouse_spending_percent"])
    if profile == "smile":
        dip = int(diconf["optimization_parameters"]["smile_dip"])
        increase = int(diconf["optimization_parameters"]["smile_increase"])
        delay = int(diconf["optimization_parameters"]["smile_delay"])
    else:
        dip = 15
        increase = 12
        delay = 0

    p.setSpendingProfile(profile, survivor, dip, increase, delay)

    # Solver Options.
    p.solverOptions = diconf["solver_options"]

    # Address legacy case files.
    # Convert boolean values (True/False) to string format, but preserve string values
    withMedicare = diconf["solver_options"].get("withMedicare")
    if isinstance(withMedicare, bool):
        p.solverOptions["withMedicare"] = "loop" if withMedicare else "None"

    # Check consistency of noRothConversions.
    name = p.solverOptions.get("noRothConversions", "None")
    if name != "None" and name not in p.inames:
        raise ValueError(f"Unknown name {name} for noRothConversions.")

    # Rebase startRothConversions and yOBBBA on year change.
    thisyear = date.today().year
    year = p.solverOptions.get("startRothConversions", thisyear)
    p.solverOptions["startRothConversions"] = max(year, thisyear)
    p.yOBBBA = max(p.yOBBBA, thisyear)

    # Results.
    p.setDefaultPlots(diconf["results"]["default_plots"])

    return p
