"""

Owl/conftoml

This file contains utility functions to save case parameters.

Copyright (C) 2024 -- Martin-D. Lacasse

Disclaimer: This program comes with no guarantee. Use at your own risk.
"""

import toml as toml
from io import StringIO, BytesIO
import numpy as np
import os

from owlplanner import plan
from owlplanner import logging
from owlplanner.rates import FROM, TO


def saveConfig(plan, file, mylog):
    """
    Save case parameters and return a dictionary containing all parameters.
    """
    # np.set_printoptions(legacy='1.21')
    accountTypes = ["taxable", "tax-deferred", "tax-free"]

    diconf = {}
    diconf["Plan Name"] = plan._name

    # Basic Info.
    diconf["Basic Info"] = {
        "Status": ["unknown", "single", "married"][plan.N_i],
        "Names": plan.inames,
        "Birth year": plan.yobs.tolist(),
        "Life expectancy": plan.expectancy.tolist(),
        "Start date": plan.startDate,
    }

    # Assets.
    diconf["Assets"] = {}
    for j in range(plan.N_j):
        amounts = plan.beta_ij[:, j] / 1000
        diconf["Assets"][f"{accountTypes[j]} savings balances"] = amounts.tolist()
    if plan.N_i == 2:
        diconf["Assets"]["Beneficiary fractions"] = plan.phi_j.tolist()
        diconf["Assets"]["Spousal surplus deposit fraction"] = plan.eta

    # Wages and Contributions.
    diconf["Wages and Contributions"] = {"Contributions file name": plan.timeListsFileName}

    # Fixed Income.
    diconf["Fixed Income"] = {
        "Pension amounts": (plan.pensionAmounts / 1000).tolist(),
        "Pension ages": plan.pensionAges.tolist(),
        "Pension indexed": plan.pensionIndexed,
        "Social security amounts": (plan.ssecAmounts / 1000).tolist(),
        "Social security ages": plan.ssecAges.tolist(),
    }

    # Rates Selection.
    diconf["Rates Selection"] = {
        "Heirs rate on tax-deferred estate": float(100 * plan.nu),
        "Long-term capital gain tax rate": float(100 * plan.psi),
        "Dividend tax rate": float(100 * plan.mu),
        "TCJA expiration year": plan.yTCJA,
        "Method": plan.rateMethod,
    }
    if plan.rateMethod in ["user", "stochastic"]:
        diconf["Rates Selection"]["Values"] = (100 * plan.rateValues).tolist()
    if plan.rateMethod in ["stochastic"]:
        diconf["Rates Selection"]["Standard deviations"] = (100 * plan.rateStdev).tolist()
        diconf["Rates Selection"]["Correlations"] = plan.rateCorr.tolist()
    if plan.rateMethod in ["historical average", "historical", "histochastic"]:
        diconf["Rates Selection"]["From"] = int(plan.rateFrm)
        diconf["Rates Selection"]["To"] = int(plan.rateTo)
    else:
        diconf["Rates Selection"]["From"] = int(FROM)
        diconf["Rates Selection"]["To"] = int(TO)

    # Asset Allocation.
    diconf["Asset Allocation"] = {
        "Interpolation method": plan.interpMethod,
        "Interpolation center": float(plan.interpCenter),
        "Interpolation width": float(plan.interpWidth),
        "Type": plan.ARCoord,
    }
    if plan.ARCoord == "account":
        for accType in accountTypes:
            diconf["Asset Allocation"][accType] = plan.boundsAR[accType]
    else:
        diconf["Asset Allocation"]["generic"] = plan.boundsAR["generic"]

    # Optimization Parameters.
    diconf["Optimization Parameters"] = {
        "Spending profile": plan.spendingProfile,
        "Surviving spouse spending percent": int(100 * plan.chi),
    }
    if plan.spendingProfile == "smile":
        diconf["Optimization Parameters"]["Smile dip"] = int(plan.smileDip)
        diconf["Optimization Parameters"]["Smile increase"] = int(plan.smileIncrease)
        diconf["Optimization Parameters"]["Smile delay"] = int(plan.smileDelay)

    diconf["Optimization Parameters"]["Objective"] = plan.objective
    diconf["Solver Options"] = plan.solverOptions

    # Results.
    diconf["Results"] = {"Default plots": plan.defaultPlots}

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
            raise RuntimeError(f"Failed to save case file {filename}: {e}")
    elif isinstance(file, StringIO):
        try:
            string = toml.dumps(diconf, encoder=toml.TomlNumpyEncoder())
            file.write(string)
        except Exception as e:
            raise RuntimeError(f"Failed to save case to StringIO: {e}")
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
    mylog = logging.Logger(verbose, logstreams)

    accountTypes = ["taxable", "tax-deferred", "tax-free"]

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
            raise FileNotFoundError(f"File {filename} not found: {e}")
    elif isinstance(file, BytesIO):
        try:
            string = file.getvalue().decode("utf-8")
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError(f"Cannot read from BytesIO: {e}")
    elif isinstance(file, StringIO):
        try:
            string = file.getvalue()
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError(f"Cannot read from StringIO: {e}")
    else:
        raise ValueError(f"Type {type(file)} not a valid type")

    # Basic Info.
    name = diconf["Plan Name"]
    inames = diconf["Basic Info"]["Names"]
    # status = diconf['Basic Info']['Status']
    yobs = diconf["Basic Info"]["Birth year"]
    expectancy = diconf["Basic Info"]["Life expectancy"]
    startDate = diconf["Basic Info"].get("Start date", "today")
    icount = len(yobs)
    s = ["", "s"][icount - 1]
    mylog.vprint(f"Plan for {icount} individual{s}: {inames}.")
    p = plan.Plan(inames, yobs, expectancy, name, startDate=startDate, verbose=True, logstreams=logstreams)

    # Assets.
    balances = {}
    for acc in accountTypes:
        balances[acc] = diconf["Assets"][f"{acc} savings balances"]
    p.setAccountBalances(
        taxable=balances["taxable"], taxDeferred=balances["tax-deferred"], taxFree=balances["tax-free"]
    )
    if icount == 2:
        phi_j = diconf["Assets"]["Beneficiary fractions"]
        p.setBeneficiaryFractions(phi_j)
        eta = diconf["Assets"]["Spousal surplus deposit fraction"]
        p.setSpousalDepositFraction(eta)

    # Wages and Contributions.
    timeListsFileName = diconf["Wages and Contributions"]["Contributions file name"]
    if timeListsFileName != "None":
        if readContributions:
            if os.path.exists(timeListsFileName):
                myfile = timeListsFileName
            elif dirname != "" and os.path.exists(dirname + "/" + timeListsFileName):
                myfile = dirname + "/" + timeListsFileName
            else:
                raise FileNotFoundError(f"File '{timeListsFileName}' not found.")
            p.readContributions(myfile)
        else:
            p.timeListsFileName = timeListsFileName
            mylog.vprint(f"Ignoring to read contributions file {timeListsFileName}.")

    # Fixed Income.
    ssecAmounts = np.array(diconf["Fixed Income"]["Social security amounts"], dtype=np.float32)
    ssecAges = np.array(diconf["Fixed Income"]["Social security ages"], dtype=np.int32)
    p.setSocialSecurity(ssecAmounts, ssecAges)
    pensionAmounts = np.array(diconf["Fixed Income"]["Pension amounts"], dtype=np.float32)
    pensionAges = np.array(diconf["Fixed Income"]["Pension ages"], dtype=np.int32)
    pensionIndexed = diconf["Fixed Income"]["Pension indexed"]
    p.setPension(pensionAmounts, pensionAges, pensionIndexed)

    # Rates Selection.
    p.setDividendRate(float(diconf["Rates Selection"]["Dividend tax rate"]))
    p.setLongTermCapitalTaxRate(float(diconf["Rates Selection"]["Long-term capital gain tax rate"]))
    p.setHeirsTaxRate(float(diconf["Rates Selection"]["Heirs rate on tax-deferred estate"]))
    p.yTCJA = int(diconf["Rates Selection"]["TCJA expiration year"])

    frm = None
    to = None
    rateValues = None
    stdev = None
    rateCorr = None
    rateMethod = diconf["Rates Selection"]["Method"]
    if rateMethod in ["historical average", "historical", "histochastic"]:
        frm = diconf["Rates Selection"]["From"]
        if not isinstance(frm, int):
            frm = int(frm)
        to = int(diconf["Rates Selection"]["To"])
        if not isinstance(to, int):
            to = int(to)
    if rateMethod in ["user", "stochastic"]:
        rateValues = np.array(diconf["Rates Selection"]["Values"], dtype=np.float32)
    if rateMethod in ["stochastic"]:
        stdev = np.array(diconf["Rates Selection"]["Standard deviations"], dtype=np.float32)
        rateCorr = np.array(diconf["Rates Selection"]["Correlations"], dtype=np.float32)
    p.setRates(rateMethod, frm, to, rateValues, stdev, rateCorr)

    # Asset Allocation.
    boundsAR = {}
    p.setInterpolationMethod(
        diconf["Asset Allocation"]["Interpolation method"],
        float(diconf["Asset Allocation"]["Interpolation center"]),
        float(diconf["Asset Allocation"]["Interpolation width"]),
    )
    allocType = diconf["Asset Allocation"]["Type"]
    if allocType == "account":
        for aType in accountTypes:
            boundsAR[aType] = np.array(diconf["Asset Allocation"][aType], dtype=np.float32)

        p.setAllocationRatios(
            allocType,
            taxable=boundsAR["taxable"],
            taxDeferred=boundsAR["tax-deferred"],
            taxFree=boundsAR["tax-free"],
        )
    elif allocType == "individual" or allocType == "spouses":
        boundsAR["generic"] = np.array(diconf["Asset Allocation"]["generic"], dtype=np.float32)
        p.setAllocationRatios(
            allocType,
            generic=boundsAR["generic"],
        )
    else:
        raise ValueError(f"Unknown asset allocation type {allocType}.")

    # Optimization Parameters.
    p.objective = diconf["Optimization Parameters"]["Objective"]

    profile = diconf["Optimization Parameters"]["Spending profile"]
    survivor = int(diconf["Optimization Parameters"]["Surviving spouse spending percent"])
    if profile == "smile":
        dip = int(diconf["Optimization Parameters"]["Smile dip"])
        increase = int(diconf["Optimization Parameters"]["Smile increase"])
        delay = int(diconf["Optimization Parameters"]["Smile delay"])
    else:
        dip = 15
        increase = 12
        delay = 0

    p.setSpendingProfile(profile, survivor, dip, increase, delay)

    # Solver Options.
    p.solverOptions = diconf["Solver Options"]

    # Check consistency of noRothConversions.
    name = p.solverOptions.get("noRothConversions", "None")
    if name != "None" and name not in p.inames:
        raise ValueError(f"Unknown name {name} for noRothConversions.")

    # Results.
    p.setDefaultPlots(diconf["Results"]["Default plots"])

    return p
