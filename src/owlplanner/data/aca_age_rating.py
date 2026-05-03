"""
CMS ACA age rating factors (45 CFR 147.102, effective 2014+).

The ACA limits age rating to a 3:1 ratio (oldest to youngest adult).
Factors are normalized so that age 21 = 1.000. Age 64 is capped at 3.000.
Enrollees age 65+ are on Medicare and not subject to marketplace rating.

Source: CMS, "Age Rating Under the Affordable Care Act," Table of Relative Rates
        https://www.cms.gov/marketplace/resources/regulations-guidance
"""

from __future__ import annotations

# Age rating factors indexed by age 0–64.
# Ages 0–14 share the child rate; ages 15–17 share one rate; 18–20 share another.
# Ages 21–64 follow the published adult curve (3:1 band, age 21 baseline = 1.000).
_ACA_AGE_RATING_FACTORS = (
    # ages 0–14
    0.635, 0.635, 0.635, 0.635, 0.635,
    0.635, 0.635, 0.635, 0.635, 0.635,
    0.635, 0.635, 0.635, 0.635, 0.635,
    # ages 15–17
    0.760, 0.760, 0.760,
    # ages 18–20
    0.850, 0.850, 0.850,
    # ages 21–29
    1.000, 1.000, 1.000, 1.000,
    1.004, 1.024, 1.048, 1.087, 1.119,
    # ages 30–39
    1.135, 1.159, 1.183, 1.198, 1.214,
    1.222, 1.230, 1.246, 1.262, 1.270,
    # ages 40–49
    1.278, 1.302, 1.325, 1.357, 1.397,
    1.444, 1.500, 1.563, 1.635, 1.706,
    # ages 50–59
    1.786, 1.865, 1.952, 2.040, 2.135,
    2.230, 2.333, 2.437, 2.548, 2.651,
    # ages 60–64
    2.754, 2.825, 2.897, 2.944, 3.000,
)

# Dict lookup: age → relative rating factor (ages 0–64).
ACA_AGE_RATING_FACTOR = {age: factor for age, factor in enumerate(_ACA_AGE_RATING_FACTORS)}


def couple_to_individual_fraction(age_younger: int) -> float:
    """
    Return the fraction of a couple's combined SLCSP that belongs to the
    younger partner's individual plan, evaluated at the moment the older
    partner turns 65 (Medicare-eligible).

    Uses the CMS age rating curve: the older partner is always age 65 (factor = 3.000)
    and the younger partner is ``age_younger`` (0 <= age_younger <= 64).

    Parameters
    ----------
    age_younger : int
        Age of the younger partner at the time the older partner turns 65.

    Returns
    -------
    float
        Fraction in (0, 1): ``f_younger / (f_older + f_younger)``.
    """
    age_younger = max(0, min(64, int(age_younger)))
    f_older = ACA_AGE_RATING_FACTOR[64]   # 3.000 (age-64 rate applies at Medicare cutoff)
    f_younger = ACA_AGE_RATING_FACTOR[age_younger]
    return f_younger / (f_older + f_younger)
