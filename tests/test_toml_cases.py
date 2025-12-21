
import owlplanner as owl


def getWaC(exdir, base):
    import os
    wac = base.replace('case_', '')
    wac = wac.replace('-spending', '')
    wac = wac.replace('-bequest', '')
    wac = exdir + wac + '.xlsx'
    if os.path.exists(wac):
        return wac
    else:
        return ''


def test_allcases():
    exdir = './examples/'
    for case in ['Case_john+sally',
                 'Case_jack+jill',
                 'Case_joe',
                 'Case_kim+sam-spending',
                 'Case_kim+sam-bequest']:
        p = owl.readConfig(exdir + case)
        wac = getWaC(exdir, case)
        if wac != '':
            p.readContributions(wac)
        p.resolve()


def test_historical():
    exdir = './examples/'
    case = 'Case_jack+jill'
    p = owl.readConfig(exdir + case)
    wac = getWaC(exdir, case)
    if wac != '':
        p.readContributions(wac)
    options = p.solverOptions
    objective = p.objective
    p.runHistoricalRange(objective, options, 1969, 2023)


def test_MC():
    exdir = './examples/'
    case = 'Case_jack+jill'
    p = owl.readConfig(exdir + case)
    wac = getWaC(exdir, case)
    if wac != '':
        p.readContributions(wac)
    options = p.solverOptions
    objective = p.objective
    p.runMC(objective, options, 20)
