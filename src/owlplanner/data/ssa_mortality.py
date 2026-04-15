"""
SSA 2025 Period Life Table mortality data and sampling utilities.

Source: Social Security Administration, Actuarial Life Table (2025).
        https://www.ssa.gov/oact/STATS/table4c6.html
        "Death probabilities (q_x) are the probabilities that an individual
        who has reached exact age x will die within one year."

Values are indexed by age: index 0 = exact age 0, index 119 = exact age 119.
Age 119 is set to 1.0 (certain death by age 120).

Copyright (C) 2025-2026 The Owlplanner Authors
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

# fmt: off
# SSA 2025 Period Life Table: q_x (annual death probability) by age
# Source: Social Security Administration, Actuarial Life Table (2025)
#         https://www.ssa.gov/oact/STATS/table4c6.html
# Ages 0–119; q_119 = 1.0 by convention.

_MALE_QX = [
    0.006064, 0.000491, 0.000309, 0.000248, 0.000199,  # 0–4
    0.000167, 0.000143, 0.000126, 0.000121, 0.000121,  # 5–9
    0.000127, 0.000143, 0.000171, 0.000227, 0.000320,  # 10–14
    0.000451, 0.000622, 0.000826, 0.001026, 0.001182,  # 15–19
    0.001301, 0.001404, 0.001498, 0.001586, 0.001679,  # 20–24
    0.001776, 0.001881, 0.001985, 0.002095, 0.002219,  # 25–29
    0.002332, 0.002445, 0.002562, 0.002653, 0.002716,  # 30–34
    0.002791, 0.002894, 0.002994, 0.003091, 0.003217,  # 35–39
    0.003353, 0.003499, 0.003642, 0.003811, 0.003996,  # 40–44
    0.004175, 0.004388, 0.004666, 0.004973, 0.005305,  # 45–49
    0.005666, 0.006069, 0.006539, 0.007073, 0.007675,  # 50–54
    0.008348, 0.009051, 0.009822, 0.010669, 0.011548,  # 55–59
    0.012458, 0.013403, 0.014450, 0.015571, 0.016737,  # 60–64
    0.017897, 0.019017, 0.020213, 0.021569, 0.023088,  # 65–69
    0.024828, 0.026705, 0.028761, 0.031116, 0.033861,  # 70–74
    0.037088, 0.041126, 0.045241, 0.049793, 0.054768,  # 75–79
    0.060660, 0.067027, 0.073999, 0.081737, 0.090458,  # 80–84
    0.100525, 0.111793, 0.124494, 0.138398, 0.153207,  # 85–89
    0.169704, 0.187963, 0.208395, 0.230808, 0.253914,  # 90–94
    0.277402, 0.300882, 0.324326, 0.347332, 0.369430,  # 95–99
    0.391927, 0.414726, 0.437722, 0.460800, 0.483840,  # 100–104
    0.508032, 0.533434, 0.560105, 0.588111, 0.617516,  # 105–109
    0.648392, 0.680812, 0.714852, 0.750595, 0.788125,  # 110–114
    0.827531, 0.868907, 0.912353, 0.957970, 1.000000,  # 115–119
]

_FEMALE_QX = [
    0.005119, 0.000398, 0.000240, 0.000198, 0.000160,  # 0–4
    0.000134, 0.000118, 0.000109, 0.000106, 0.000106,  # 5–9
    0.000111, 0.000121, 0.000140, 0.000162, 0.000188,  # 10–14
    0.000224, 0.000276, 0.000337, 0.000395, 0.000450,  # 15–19
    0.000496, 0.000532, 0.000567, 0.000610, 0.000650,  # 20–24
    0.000699, 0.000743, 0.000796, 0.000855, 0.000924,  # 25–29
    0.000988, 0.001053, 0.001123, 0.001198, 0.001263,  # 30–34
    0.001324, 0.001403, 0.001493, 0.001596, 0.001700,  # 35–39
    0.001803, 0.001905, 0.002009, 0.002116, 0.002223,  # 40–44
    0.002352, 0.002516, 0.002712, 0.002936, 0.003177,  # 45–49
    0.003407, 0.003642, 0.003917, 0.004238, 0.004619,  # 50–54
    0.005040, 0.005493, 0.005987, 0.006509, 0.007067,  # 55–59
    0.007658, 0.008305, 0.008991, 0.009681, 0.010343,  # 60–64
    0.011018, 0.011743, 0.012532, 0.013512, 0.014684,  # 65–69
    0.016025, 0.017468, 0.019195, 0.021195, 0.023452,  # 70–74
    0.025980, 0.029153, 0.032394, 0.035888, 0.039676,  # 75–79
    0.044156, 0.049087, 0.054635, 0.061066, 0.068431,  # 80–84
    0.076841, 0.086205, 0.096851, 0.109019, 0.121867,  # 85–89
    0.135805, 0.151108, 0.168020, 0.186340, 0.206432,  # 90–94
    0.228086, 0.250406, 0.273699, 0.296984, 0.319502,  # 95–99
    0.342716, 0.366532, 0.390844, 0.415531, 0.440463,  # 100–104
    0.466891, 0.494904, 0.524599, 0.556075, 0.589439,  # 105–109
    0.624805, 0.662294, 0.702031, 0.744153, 0.788125,  # 110–114
    0.827531, 0.868907, 0.912353, 0.957970, 1.000000,  # 115–119
]
# fmt: on

_QX = {"M": np.array(_MALE_QX), "F": np.array(_FEMALE_QX)}

_MAX_AGE = 119


def survival_pmf(sex, current_age):
    """
    Return (ages, pmf) arrays for the discrete lifespan distribution,
    conditional on being alive at current_age.

    Parameters
    ----------
    sex : str
        'M' for male, 'F' for female.
    current_age : int
        Current age in whole years (must be <= _MAX_AGE).

    Returns
    -------
    ages : np.ndarray of int
        Ages at death, from current_age to _MAX_AGE inclusive.
    pmf : np.ndarray of float
        Probability of dying at each age (sums to 1.0).
    """
    if sex not in _QX:
        raise ValueError(f"sex must be 'M' or 'F', got {sex!r}")
    if not (0 <= current_age <= _MAX_AGE):
        raise ValueError(f"current_age must be in [0, {_MAX_AGE}], got {current_age}")

    qx = _QX[sex]
    ages = np.arange(current_age, _MAX_AGE + 1, dtype=int)

    # Survival to each age, conditional on being alive at current_age
    # S(x | age0) = prod_{j=age0}^{x-1} (1 - q_j)
    log_survival = np.concatenate([[0.0], np.cumsum(np.log1p(-qx[current_age:_MAX_AGE]))])
    survival = np.exp(log_survival)  # shape: len(ages)

    pmf = survival * qx[current_age: _MAX_AGE + 1]
    pmf = pmf / pmf.sum()  # normalize to correct floating-point drift
    return ages, pmf


def sample_lifespans(sex, current_age, n, rng=None):
    """
    Draw n random lifespans (age at death) from the SSA period life table,
    conditional on being alive at current_age.

    Parameters
    ----------
    sex : str
        'M' for male, 'F' for female.
    current_age : int
        Current age in whole years.
    n : int
        Number of samples to draw.
    rng : np.random.Generator or None
        Random number generator. If None, uses np.random.default_rng().

    Returns
    -------
    lifespans : np.ndarray of int, shape (n,)
        Sampled ages at death.
    """
    if rng is None:
        rng = np.random.default_rng()
    ages, pmf = survival_pmf(sex, current_age)
    return rng.choice(ages, size=n, replace=True, p=pmf)


def life_expectancy(sex, current_age):
    """
    Return the conditional life expectancy E[T | alive at current_age].

    Parameters
    ----------
    sex : str
        'M' for male, 'F' for female.
    current_age : int
        Current age in whole years.

    Returns
    -------
    float
        Expected age at death given survival to current_age.
    """
    ages, pmf = survival_pmf(sex, current_age)
    return float(np.dot(ages, pmf))
