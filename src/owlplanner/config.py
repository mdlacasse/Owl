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


def saveConfig(myplan, file, mylog):
    """
    Save case parameters and return a dictionary containing all parameters.
    """
    # np.set_printoptions(legacy='1.21')
    accountTypes = ["taxable", "tax-deferred", "tax-free"]

    diconf = {}
    diconf["Plan Name"] = myplan._name
    diconf["Description"] = myplan._description

    # Basic Info.
    diconf["Basic Info"] = {
        "Status": ["unknown", "single", "married"][myplan.N_i],
        "Names": myplan.inames,
        "Birth year": myplan.yobs.tolist(),
        "Life expectancy": myplan.expectancy.tolist(),
        "Start date": myplan.startDate,
    }

    # Assets.
    diconf["Assets"] = {}
    for j in range(myplan.N_j):
        amounts = myplan.beta_ij[:, j] / 1000
        diconf["Assets"][f"{accountTypes[j]} savings balances"] = amounts.tolist()
    if myplan.N_i == 2:
        diconf["Assets"]["Beneficiary fractions"] = myplan.phi_j.tolist()
        diconf["Assets"]["Spousal surplus deposit fraction"] = myplan.eta

    # Wages and Contributions.
    diconf["Wages and Contributions"] = {"Contributions file name": myplan.timeListsFileName}

    # Fixed Income.
    diconf["Fixed Income"] = {
        "Pension amounts": (myplan.pensionAmounts / 1000).tolist(),
        "Pension ages": myplan.pensionAges.tolist(),
        "Pension indexed": myplan.pensionIndexed,
        "Social security amounts": (myplan.ssecAmounts / 1000).tolist(),
        "Social security ages": myplan.ssecAges.tolist(),
    }

    # Rates Selection.
    diconf["Rates Selection"] = {
        "Heirs rate on tax-deferred estate": float(100 * myplan.nu),
        "Long-term capital gain tax rate": float(100 * myplan.psi),
        "Dividend tax rate": float(100 * myplan.mu),
        "TCJA expiration year": myplan.yTCJA,
        "Method": myplan.rateMethod,
    }
    if myplan.rateMethod in ["user", "stochastic"]:
        diconf["Rates Selection"]["Values"] = (100 * myplan.rateValues).tolist()
    if myplan.rateMethod in ["stochastic"]:
        diconf["Rates Selection"]["Standard deviations"] = (100 * myplan.rateStdev).tolist()
        diconf["Rates Selection"]["Correlations"] = myplan.rateCorr.tolist()
    if myplan.rateMethod in ["historical average", "historical", "histochastic"]:
        diconf["Rates Selection"]["From"] = int(myplan.rateFrm)
        diconf["Rates Selection"]["To"] = int(myplan.rateTo)
    else:
        diconf["Rates Selection"]["From"] = int(FROM)
        diconf["Rates Selection"]["To"] = int(TO)

    # Asset Allocation.
    diconf["Asset Allocation"] = {
        "Interpolation method": myplan.interpMethod,
        "Interpolation center": float(myplan.interpCenter),
        "Interpolation width": float(myplan.interpWidth),
        "Type": myplan.ARCoord,
    }
    if myplan.ARCoord == "account":
        for accType in accountTypes:
            diconf["Asset Allocation"][accType] = myplan.boundsAR[accType]
    else:
        diconf["Asset Allocation"]["generic"] = myplan.boundsAR["generic"]

    # Optimization Parameters.
    diconf["Optimization Parameters"] = {
        "Spending profile": myplan.spendingProfile,
        "Surviving spouse spending percent": int(100 * myplan.chi),
    }
    if myplan.spendingProfile == "smile":
        diconf["Optimization Parameters"]["Smile dip"] = int(myplan.smileDip)
        diconf["Optimization Parameters"]["Smile increase"] = int(myplan.smileIncrease)
        diconf["Optimization Parameters"]["Smile delay"] = int(myplan.smileDelay)

    diconf["Optimization Parameters"]["Objective"] = myplan.objective
    diconf["Solver Options"] = myplan.solverOptions

    # Results.
    diconf["Results"] = {"Default plots": myplan.defaultPlots}

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
    p._description = diconf.get("Description", "")

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
