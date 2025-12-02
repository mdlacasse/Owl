"""

Owl/socialsecurity
--------

A retirement planner using linear programming optimization.

This file contains the rules related to social security.

Copyright &copy; 2025 - Martin-D. Lacasse

Disclaimers: This code is for educational purposes only and does not constitute financial advice.

"""

import numpy as np


def getFRAs(yobs):
    """
    Return full retirement age based on birth year.
    Returns an array of fractional age.
    """
    fras = np.zeros(len(yobs))

    for i in range(len(yobs)):
        if yobs[i] >= 1960:
            fras[i] = 67
        else:
            mo = max(0, 2*(yobs[i] - 1954))
            fras[i] = 66 + mo/12

    return fras


def getSpousalBenefits(pias):
    """
    Compute spousal benefit. Returns an array.
    """
    icount = len(pias)
    benefits = np.zeros(icount)
    if icount == 1:
        return benefits
    elif icount == 2:
        for i in range(2):
            j = (i+1) % 2
            benefits[i] = max(0, 0.5*pias[j] - pias[i])
    else:
        raise ValueError(f"PIAs array cannot have {icount} entries.")

    return benefits


def getSelfFactor(fra, age):
    """
    Return factor to multiply PIA given the age when SS starts.
    Year of FRA and age can be fractional.
    """
    if age < 62 or age > 70:
        raise ValueError(f"Age {age} out of range.")

    diff = fra - age
    if diff <= 0:
        return 1. - .08 * diff
    elif diff <= 3:
        # Reduction of 20% over first 36 months.
        return 1. - 0.06666667 * diff
    else:
        # Then 5% per tranche of 12 months.
        return .8 - 0.05 * (diff - 3)


def getSpousalFactor(fra, age):
    """
    Return factor to multiply spousal benefit given the age when benefit starts.
    Year of FRA and age can be fractional.
    """
    if age < 62:
        raise ValueError(f"Age {age} out of range.")

    diff = fra - age
    if diff <= 0:
        return 1.
    elif diff <= 3:
        # Reduction of 25% over first 36 months.
        return 1. - 0.08333333 * diff
    else:
        # Then 5% per tranche of 12 months.
        return .75 - 0.05 * (diff - 3)
