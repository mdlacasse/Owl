
import owlplanner as owl


def test_allcases():
    exdir = './examples/'
    for case in ['case_john+sally',
                 'case_jack+jill',
                 'case_kim+sam-spending',
                 'case_kim+sam-bequest']:
        p = owl.readConfig(exdir + case)
        p.resolve()
