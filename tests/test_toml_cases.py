
import owlplanner as owl


def test_allcases():
    exdir = './examples/'
    for case in ['case_john+sally',
                 'case_jack+jill',
                 'case_joe',
                 'case_kim+sam-spending',
                 'case_kim+sam-bequest']:
        p = owl.readConfig(exdir + case)
        p.resolve()


def test_historical():
    exdir = './examples/'
    case = 'case_jack+jill'
    p = owl.readConfig(exdir + case)
    options = p.solverOptions
    objective = p.objective
    p.runHistoricalRange(objective, options, 1969, 2023)


def test_MC():
    exdir = './examples/'
    case = 'case_jack+jill'
    p = owl.readConfig(exdir + case)
    options = p.solverOptions
    objective = p.objective
    p.runMC(objective, options, 20)
