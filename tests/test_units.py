
from owlplanner import utils as u


def test_rounding():
    number = 1500000.
    number = u.roundCents(number)
    assert number == number
    number = -1500000.
    number = u.roundCents(number)
    assert number == number
