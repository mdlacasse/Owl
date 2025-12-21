import os

import owlplanner as owl


def getHFP(exdir, case):
    wac = case.replace("Case_", "HFP_")
    wac = wac.replace("-spending", "")
    wac = wac.replace("-bequest", "")
    wac = os.path.join(exdir,  wac + ".xlsx")
    if os.path.exists(wac):
        return wac
    else:
        return ""


def test_allcases():
    exdir = "./examples/"
    for case in ["Case_john+sally",
                 "Case_jack+jill",
                 "Case_joe",
                 "Case_kim+sam-spending",
                 "Case_kim+sam-bequest"]:
        file = os.path.join(exdir, case)
        p = owl.readConfig(file)
        wac = getHFP(exdir, case)
        if wac != "":
            p.readContributions(wac)
        else:
            assert False
        p.resolve()


def test_historical():
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    p = owl.readConfig(file)
    wac = getHFP(exdir, case)
    if wac != "":
        p.readContributions(wac)
    options = p.solverOptions
    objective = p.objective
    p.runHistoricalRange(objective, options, 1969, 2023)


def test_MC():
    exdir = "./examples/"
    case = "Case_jack+jill"
    file = os.path.join(exdir, case)
    p = owl.readConfig(file)
    wac = getHFP(exdir, case)
    if wac != "":
        p.readContributions(wac)
    options = p.solverOptions
    objective = p.objective
    p.runMC(objective, options, 20)
