"""
Social Security benefit calculation rules and utilities.

This module implements Social Security rules including full retirement age
calculations, benefit computations, and related retirement planning functions.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import numpy as np
from datetime import date

# SSA-mandated benefit reduction rates (own-benefit and spousal, first 36 months before FRA).
# Expressed as a per-year rate since 'diff' (fra - ssage) is measured in years.
_SELF_REDUCTION_RATE = 5 / 9 / 100 * 12       # 5/9 of 1% per month × 12 ≈ 0.06667/yr (own benefit)
_SPOUSAL_REDUCTION_RATE = 25 / 36 / 100 * 12  # 25/36 of 1% per month × 12 ≈ 0.08333/yr (spousal)


def _ssa_age(convage, bornOnFirstDays):
    """Convert conventional age to SSA age (adds 1/12 if born on the 1st of the month).

    Per SSA rules (POMS RS 00615.015), a person born on the 1st attains their age on the
    last day of the prior month, so at any conventional age X they have been that age for
    one extra month relative to someone born mid-month.  Born-on-2nd attains age on the
    1st of the birth month — no prior-month shift, so no adjustment is applied.
    """
    return convage + (1/12 if bornOnFirstDays else 0)


def _reduction_factor(diff, delay_rate, first_36_rate, base_at_3):
    """
    Return benefit factor given FRA-minus-SSA-age difference and reduction parameters.

    Parameters
    ----------
    diff : float
        FRA minus SSA claiming age (negative = claiming after FRA).
    delay_rate : float
        Increase rate per year for claiming after FRA (0.08 for own benefit, 0 for spousal).
    first_36_rate : float
        Reduction rate per year for the first 36 months before FRA.
    base_at_3 : float
        Benefit factor at exactly 3 years before FRA (transition point to the slower rate).
    """
    if diff <= 0:
        return 1.0 - delay_rate * diff
    elif diff <= 3:
        return 1.0 - first_36_rate * diff
    else:
        return base_at_3 - 0.05 * (diff - 3)


def getFRAs(yobs):
    """
    Return full retirement age (FRA) based on birth year.

    The FRA is determined by birth year according to Social Security rules:
    - Birth year >= 1960: FRA is 67
    - Birth year 1955–1959: FRA increases by 2 months for each year after 1954 (66+2/12 to 66+10/12)
    - Birth year 1943–1954: FRA is 66
    - Birth year 1938–1942: FRA increases by 2 months for each year after 1937 (65+2/12 to 65+10/12)
    - Birth year <= 1937: FRA is 65

    Parameters
    ----------
    yobs : array-like
        Array of birth years, one for each individual.

    Returns
    -------
    numpy.ndarray
        Array of FRA values in fractional years (1/12 increments), one for each individual.
        Ages are returned in Social Security age format. Comparisons to FRA should be
        done using Social Security age (which accounts for birthday-on-first adjustments).
    """
    fras = np.zeros(len(yobs))

    for i in range(len(yobs)):
        if yobs[i] >= 1960:
            fras[i] = 67
        elif yobs[i] >= 1955:
            fras[i] = 66 + 2*(yobs[i] - 1954)/12
        elif yobs[i] >= 1943:
            fras[i] = 66
        elif yobs[i] >= 1938:
            fras[i] = 65 + 2*(yobs[i] - 1937)/12
        else:
            fras[i] = 65

    return fras


def getSurvivorFRAs(yobs):
    """
    Return survivor full retirement age (FRA) based on birth year.

    The survivor FRA schedule is distinct from the retirement FRA schedule and is shifted
    approximately 2 birth-year cohorts later, per the 1983 Social Security Amendments.

    - Birth year >= 1962: FRA is 67
    - Birth year 1957–1961: FRA increases by 2 months per year (66+2/12 to 66+10/12)
    - Birth year 1945–1956: FRA is 66
    - Birth year 1940–1944: FRA increases by 2 months per year (65+2/12 to 65+10/12)
    - Birth year <= 1939: FRA is 65

    Parameters
    ----------
    yobs : array-like
        Array of birth years, one for each individual.

    Returns
    -------
    numpy.ndarray
        Array of survivor FRA values in fractional years (1/12 increments).
    """
    fras = np.zeros(len(yobs))

    for i in range(len(yobs)):
        if yobs[i] >= 1962:
            fras[i] = 67
        elif yobs[i] >= 1957:
            fras[i] = 66 + 2 * (yobs[i] - 1956) / 12
        elif yobs[i] >= 1945:
            fras[i] = 66
        elif yobs[i] >= 1940:
            fras[i] = 65 + 2 * (yobs[i] - 1939) / 12
        else:
            fras[i] = 65

    return fras


def _survivor_factor(survivor_fra, survivor_age):
    """
    Return the benefit factor for a survivor claiming before their survivor FRA.

    Per SSA rules, a survivor claiming between age 60 and their survivor FRA receives a
    reduced benefit, linearly interpolated from 100% at survivor FRA down to 71.5% at 60.
    At or above survivor FRA the factor is 1.0; at age 60 it is always 0.715 regardless
    of which survivor FRA schedule applies.

    Parameters
    ----------
    survivor_fra : float
        Survivor full retirement age in fractional years.
    survivor_age : float
        Survivor's age (fractional years) at the time the survivor benefit begins.
    """
    if survivor_age >= survivor_fra:
        return 1.0
    return 1.0 - 0.285 * (survivor_fra - survivor_age) / (survivor_fra - 60)


def getSpousalBenefits(pias):
    """
    Compute the maximum spousal benefit amount for each individual.

    The spousal benefit is calculated as 50% of the spouse's Primary Insurance Amount (PIA),
    minus the individual's own PIA. The result is the additional benefit the individual
    would receive as a spouse, which cannot be negative.

    Note: This calculation is not affected by which day of the month is the birthday.

    Parameters
    ----------
    pias : array-like
        Array of Primary Insurance Amounts (monthly benefit at FRA), one for each individual.
        Must have exactly 1 or 2 entries.

    Returns
    -------
    numpy.ndarray
        Array of spousal benefit amounts (monthly), one for each individual.
        For a single individual, returns [0].
        For two individuals, returns the additional spousal benefit each would receive
        (which is max(0, 0.5 * spouse_PIA - own_PIA)).

    Raises
    ------
    ValueError
        If the pias array does not have exactly 1 or 2 entries.
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


def getSelfFactor(fra, convage, bornOnFirstDays):
    """
    Return the reduction/increase factor to multiply PIA based on claiming age.

    This function calculates the adjustment factor for self benefits based on when
    Social Security benefits start relative to Full Retirement Age (FRA):
    - Before FRA: Benefits are reduced (minimum 70% at age 62)
    - At FRA: Full benefit (100% of PIA)
    - After FRA: Benefits are increased by 8% per year (up to 132% at age 70)

    The function automatically adjusts for Social Security age if the birthday is on
    the 1st day of the month (adds 1/12 year to conventional age).  Per POMS RS 00615.015,
    born-on-1st individuals attain each age on the last day of the prior month, so at any
    given conventional age they have been that age one month longer.  Born-on-2nd attains
    age on the 1st of the birth month — no prior-month shift, so no adjustment is applied.

    Parameters
    ----------
    fra : float
        Full Retirement Age in years (can be fractional with 1/12 increments).
    convage : float
        Conventional age when benefits start, in years (can be fractional with 1/12 increments).
        Must be between 62 and 70 inclusive.
    bornOnFirstDays : bool
        True if birthday is on the 1st day of the month only, False otherwise (including 2nd).
        If True, 1/12 year is added to convert conventional age to SSA age.

    Returns
    -------
    float
        Factor to multiply PIA. Examples:
        - 0.75 = 75% of PIA (claiming at 62 with FRA of 66)
        - 1.0 = 100% of PIA (claiming at FRA)
        - 1.32 = 132% of PIA (claiming at 70 with FRA of 66)

    Raises
    ------
    ValueError
        If convage is less than 62 or greater than 70.
    """
    if convage < 62 or convage > 70:
        raise ValueError(f"Age {convage} out of range.")

    diff = fra - _ssa_age(convage, bornOnFirstDays)
    return _reduction_factor(diff, 0.08, _SELF_REDUCTION_RATE, 0.8)


def getSpousalFactor(fra, convage, bornOnFirstDays):
    """
    Return the reduction factor to multiply spousal benefits based on claiming age.

    This function calculates the adjustment factor for spousal benefits based on when
    benefits start relative to Full Retirement Age (FRA):
    - Before FRA: Benefits are reduced (minimum 32.5% at age 62)
    - At or after FRA: Full spousal benefit (50% of spouse's PIA, no increase for delay)

    The function automatically adjusts for Social Security age if the birthday is on
    the 1st day of the month (adds 1/12 year to conventional age).  Per POMS RS 00615.015,
    born-on-1st individuals attain each age on the last day of the prior month, so at any
    given conventional age they have been that age one month longer.  Born-on-2nd attains
    age on the 1st of the birth month — no prior-month shift, so no adjustment is applied.

    Parameters
    ----------
    fra : float
        Full Retirement Age in years (can be fractional with 1/12 increments).
    convage : float
        Conventional age when benefits start, in years (can be fractional with 1/12 increments).
        Must be at least 62 (no maximum, but no increase beyond FRA).
    bornOnFirstDays : bool
        True if birthday is on the 1st day of the month only, False otherwise (including 2nd).
        If True, 1/12 year is added to convert conventional age to SSA age.

    Returns
    -------
    float
        Factor to multiply spousal benefit. Examples:
        - 0.70 = 70% of spousal benefit (claiming at 62 with FRA of 66)
        - 0.65 = 65% of spousal benefit (claiming at 62 with FRA of 67)
        - 1.0 = 100% of spousal benefit (claiming at or after FRA)
        Note: Unlike self benefits, spousal benefits do not increase beyond FRA.

    Raises
    ------
    ValueError
        If convage is less than 62.
    """
    if convage < 62:
        raise ValueError(f"Age {convage} out of range.")

    diff = fra - _ssa_age(convage, bornOnFirstDays)
    return _reduction_factor(diff, 0.0, _SPOUSAL_REDUCTION_RATE, 0.75)


def _add_spousal_benefit(zeta_in, i, nd, spousal_amount, fra, yobs, mobs, ages, tobs, thisyear):
    """
    Apply spousal benefit to zeta_in[i, :] starting from the later of both spouses' claim dates.

    The spousal benefit begins when the last spouse has started collecting (since the
    spousal benefit requires the higher-earning spouse to be collecting first).
    """
    latest_claim_year = float(np.max(yobs + (mobs - 1) / 12 + ages))
    claim_age = latest_claim_year - yobs[i] - (mobs[i] - 1) / 12
    payment_claim_year = latest_claim_year + 1/12
    ns2 = max(0, int(payment_claim_year) - thisyear)
    spousal_factor = getSpousalFactor(fra, claim_age, bool(tobs[i] == 1))
    zeta_in[i, ns2:nd] += spousal_amount * spousal_factor
    zeta_in[i, ns2] -= spousal_amount * spousal_factor * (payment_claim_year % 1.)


def _apply_survivor_benefit(zeta_in, earlier_idx, survivor_idx, death_year_n, survivor_horizon,
                            pia_earlier, survivor_factor):
    """Assign the surviving spouse's benefit from the year of first death onward.

    Two SSA rules are applied in order:
    1. 82.5% PIA floor (CFR § 404.391): survivor receives max(deceased actual, 0.825 × PIA).
    2. Survivor claiming-age reduction: if the survivor is below their survivor FRA at the
       time of death, the benefit is further reduced linearly toward 71.5% at age 60.

    Note: zeta_in is still in monthly units here (×12 annualisation happens after this call),
    so pia_earlier is also monthly.
    """
    deceased_benefit = zeta_in[earlier_idx, death_year_n - 1]
    survivor_benefit = max(deceased_benefit, 0.825 * pia_earlier) * survivor_factor
    zeta_in[survivor_idx, death_year_n:survivor_horizon] = survivor_benefit


def compute_social_security_benefits(pias, ages, yobs, mobs, tobs, horizons, N_i, N_n,
                                     trim_pct=0, trim_year=None, thisyear=None):
    """
    Compute annual Social Security benefits by individual and year.

    Benefits are paid in arrears (one month after eligibility). Handles own benefits,
    spousal benefits, survivor benefits, and optional trim. Ages may be adjusted for
    eligibility (e.g. reset to 62 if below).

    Parameters
    ----------
    pias : array
        Primary Insurance Amounts (monthly), one per individual
    ages : array
        Claiming ages, one per individual (may be modified for eligibility)
    yobs : array
        Birth years, one per individual
    mobs : array
        Birth months (1-12), one per individual
    tobs : array
        Birth day-of-month, one per individual (1-2 treated specially per SSA)
    horizons : array
        Year index when each individual's horizon ends
    N_i : int
        Number of individuals
    N_n : int
        Plan horizon (number of years)
    trim_pct : float
        Percent reduction in benefits from trim_year onward (0 = no trim)
    trim_year : int or None
        Calendar year when trim begins (required if trim_pct > 0)
    thisyear : int or None
        Current calendar year (default: date.today().year)

    Returns
    -------
    zeta_in : ndarray
        Shape (N_i, N_n), annual SS benefits per individual per year
    ages : ndarray
        Claiming ages, possibly adjusted for eligibility
    """
    if thisyear is None:
        thisyear = date.today().year

    pias = np.asarray(pias, dtype=np.int32)
    ages = np.asarray(ages, dtype=np.float64).copy()

    # Identify which spouse dies first (shorter horizon) so survivor benefit can be applied later.
    if N_i == 2 and np.min(horizons) != np.max(horizons):
        death_year_n = int(np.min(horizons))
        earlier_idx = int(np.argmax(horizons == death_year_n))
        survivor_idx = (earlier_idx + 1) % 2
    else:
        death_year_n = N_n
        earlier_idx = 0
        survivor_idx = -1

    fras = getFRAs(yobs)
    spousalBenefits = getSpousalBenefits(pias)

    zeta_in = np.zeros((N_i, N_n))
    for i in range(N_i):
        # Eligibility: born on 1st or 2nd can claim in their birthday month (or prior for 1st).
        # Factor shift: only born on 1st attains age one month early, warranting +1/12 SSA age.
        bornOnFirstDays = (tobs[i] <= 2)
        bornOnFirst = (tobs[i] == 1)
        eligible = 62 if bornOnFirstDays else 62 + 1/12
        if round(ages[i] * 12) < round(eligible * 12):
            ages[i] = eligible

        janage = ages[i] + (mobs[i] - 1) / 12
        paymentJanage = janage + 1/12
        paymentIage = int(paymentJanage)
        payment_start_n = yobs[i] + paymentIage - thisyear
        ns = max(0, payment_start_n)
        nd = horizons[i]
        zeta_in[i, ns:nd] = pias[i]
        if payment_start_n >= 0:
            zeta_in[i, ns] *= 1 - (paymentJanage % 1.)

        zeta_in[i, :] *= getSelfFactor(fras[i], ages[i], bornOnFirst)

        if N_i == 2 and spousalBenefits[i] > 0:
            _add_spousal_benefit(zeta_in, i, nd, spousalBenefits[i],
                                 fras[i], yobs, mobs, ages, tobs, thisyear)

    if N_i == 2 and death_year_n < N_n:
        # Compute the survivor's age at the death year to apply the claiming-age reduction.
        survivor_fra = getSurvivorFRAs([yobs[survivor_idx]])[0]
        survivor_age_at_death = ((thisyear + death_year_n) - yobs[survivor_idx]
                                 - (mobs[survivor_idx] - 1) / 12)
        survivor_factor = _survivor_factor(survivor_fra, survivor_age_at_death)
        # Effective benefit: 82.5% PIA floor first, then survivor claiming-age reduction.
        deceased_effective = max(zeta_in[earlier_idx, death_year_n - 1], 0.825 * pias[earlier_idx])
        if deceased_effective * survivor_factor > zeta_in[survivor_idx, death_year_n - 1]:
            _apply_survivor_benefit(zeta_in, earlier_idx, survivor_idx, death_year_n,
                                    horizons[survivor_idx], pias[earlier_idx], survivor_factor)

    zeta_in *= 12

    if trim_pct > 0 and trim_year is not None:
        trim = 1.0 - trim_pct / 100
        trim_n = max(0, trim_year - thisyear)
        if 0 <= trim_n < N_n:
            zeta_in[:, trim_n:] *= trim

    return zeta_in, ages
