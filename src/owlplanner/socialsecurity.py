"""
Social Security benefit calculation rules and utilities.

This module implements Social Security rules including full retirement age
calculations, benefit computations, and related retirement planning functions.

Limitations and known omissions:

- SSA family maximum (CFR § 404.403) is not modeled. When multiple beneficiaries
  are entitled on one worker's record, SSA may reduce total benefits. Omission of
  this cap may overstate benefits (and thus understate taxes) in some cases, though
  it typically affects only workers with high PIAs and multiple auxiliaries.

- WEP (Windfall Elimination Provision) and GPO (Government Pension Offset) are not
  modeled. Both were fully repealed by the Social Security Fairness Act (signed
  January 5, 2025), effective for benefits payable January 2024 and later.
  No modeling is required.

- Earnings test not modeled: the SSA earnings test withholds benefits for recipients
  below FRA who earn above an annual threshold (e.g., $24,480 in 2026 for those
  under FRA all year). This tool assumes users are retired with no earned income
  above the exempt amount.

- Survivor benefit timing: the date at which the survivor claims the survivor benefit
  is a user setting (``survivor_claim_age``), not an optimized decision. Owl models
  the survivor's own benefit and the survivor benefit as two independent streams and
  pays the greater of the two in each year, so switching strategies (e.g. take the
  survivor benefit at 60 and let one's own benefit grow to 70) are represented, but
  the best claiming date is not searched for automatically.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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

Public API (used by plan.py): getFRAs, compute_social_security_benefits,
build_own_benefit_table, compute_survivor_stream, apply_survivor_to_benefit_table,
validate_survivor_claim_age.
All other functions are internal and may change without notice.
"""

__all__ = [
    "getFRAs",
    "getSurvivorFRAs",
    "compute_social_security_benefits",
    "build_own_benefit_table",
    "compute_survivor_stream",
    "survivor_claim_window",
    "apply_survivor_to_benefit_table",
    "validate_survivor_claim_age",
]

import numpy as np
from datetime import date
from typing import NamedTuple

# SSA-mandated benefit reduction rates (own-benefit and spousal, first 36 months before FRA).
# Expressed as a per-year rate since 'diff' (fra - ssage) is measured in years.
_SELF_REDUCTION_RATE = 5 / 9 / 100 * 12  # 5/9 of 1% per month × 12 ≈ 0.06667/yr (own benefit)
_SPOUSAL_REDUCTION_RATE = 25 / 36 / 100 * 12  # 25/36 of 1% per month × 12 ≈ 0.08333/yr (spousal)


def _ssa_age(convage, bornOnFirstDays):
    """Convert conventional age to SSA age (adds 1/12 if born on the 1st of the month).

    Per SSA rules (POMS RS 00615.015), a person born on the 1st attains their age on the
    last day of the prior month, so at any conventional age X they have been that age for
    one extra month relative to someone born mid-month.  Born-on-2nd attains age on the
    1st of the birth month — no prior-month shift, so no adjustment is applied.
    """
    return convage + (1 / 12 if bornOnFirstDays else 0)


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


def getFRAs(yobs, mobs, tobs):
    """
    Return full retirement age (FRA) based on birth date.

    The FRA is determined by birth date according to Social Security rules
    (POMS RS 00615.003). Per SSA, a person born on the 1st of a month attains
    age on the last day of the prior month; for FRA boundaries, Jan 1 is
    treated as the prior year (e.g., 1/1/60 → 66+10/12; 1/2/60 → 67).
    - Birth year >= 1960 (or 1/1/60): FRA is 67 (or 66+10/12 for 1/1/60)
    - Birth year 1955–1959: FRA increases by 2 months for each year after 1954
    - Birth year 1943–1954: FRA is 66
    - Birth year 1938–1942: FRA increases by 2 months for each year after 1937
    - Birth year <= 1937: FRA is 65

    Parameters
    ----------
    yobs : array-like
        Array of birth years, one for each individual.
    mobs : array-like
        Birth months (1–12), one per individual.
    tobs : array-like
        Birth day-of-month, one per individual.

    Returns
    -------
    numpy.ndarray
        Array of FRA values in fractional years (1/12 increments), one per individual.
    """
    yobs = np.asarray(yobs)
    n = len(yobs)
    mobs = np.broadcast_to(np.asarray(mobs), n)
    tobs = np.broadcast_to(np.asarray(tobs), n)
    # Jan 1 special case: SSA treats 1/1 as prior year for FRA boundaries.
    eff_yobs = np.where((mobs == 1) & (tobs == 1), yobs - 1, yobs)

    fras = np.zeros(n)
    for i in range(n):
        y = eff_yobs[i]
        if y >= 1960:
            fras[i] = 67
        elif y >= 1955:
            fras[i] = 66 + 2 * (y - 1954) / 12
        elif y >= 1943:
            fras[i] = 66
        elif y >= 1938:
            fras[i] = 65 + 2 * (y - 1937) / 12
        else:
            fras[i] = 65
    return fras


def getSurvivorFRAs(yobs, mobs, tobs):
    """
    Return the survivor full retirement age from birth date.

    This is a *different* SSA schedule from the retirement FRA returned by :func:`getFRAs`,
    and can fall up to four months earlier for the same person: someone born in 1960 reaches
    their survivor FRA at 66 years 8 months but their retirement FRA at 67. Both are derived
    from the survivor's own birth date, and the same Jan-1 rule applies.

    A survivor benefit is reduced when claimed before this age and earns no delayed
    retirement credits after it.
    """
    yobs = np.asarray(yobs)
    n = len(yobs)
    mobs = np.broadcast_to(np.asarray(mobs), n)
    tobs = np.broadcast_to(np.asarray(tobs), n)
    eff_yobs = np.where((mobs == 1) & (tobs == 1), yobs - 1, yobs)
    fras = np.zeros(n)
    for i in range(n):
        y = eff_yobs[i]
        if y >= 1962:
            fras[i] = 67
        elif y >= 1957:
            fras[i] = 66 + 2 * (y - 1956) / 12
        elif y >= 1945:
            fras[i] = 66
        elif y >= 1940:
            fras[i] = 65 + 2 * (y - 1939) / 12
        else:
            fras[i] = 65
    return fras


def _survivor_factor(survivor_fra, survivor_age):
    """
    Return the benefit factor for a survivor claiming before their survivor FRA.

    Per SSA rules, a survivor claiming between age 60 and their survivor FRA receives a
    reduced benefit, linearly interpolated from 100% at survivor FRA down to 71.5% at 60.
    At or above survivor FRA the factor is 1.0; at age 60 it is always 0.715 regardless
    of which survivor FRA schedule applies. Survivor benefits cannot be claimed before
    age 60; ages below 60 are clamped to 60 (the SSA minimum claiming age for survivors).

    Parameters
    ----------
    survivor_fra : float
        Survivor full retirement age in fractional years.
    survivor_age : float
        Survivor's age (fractional years) at the time the survivor benefit begins.
        Values below 60 are treated as 60.
    """
    survivor_age = max(survivor_age, 60)  # Cannot claim survivor benefits before age 60
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
            j = (i + 1) % 2
            benefits[i] = max(0, 0.5 * pias[j] - pias[i])
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


def _payment_start(yob, mob, claim_age, thisyear):
    """
    Return (n_start, first_year_fraction) for a benefit claimed at ``claim_age``.

    Benefits are paid in arrears: the first check arrives the month after the claiming
    age is attained. ``n_start`` is the plan-year index of that first check (may be
    negative if it predates the plan), and ``first_year_fraction`` is the share of that
    year actually covered by payments.
    """
    janage = claim_age + (mob - 1) / 12
    payment_janage = janage + 1 / 12
    n_start = int(yob + int(payment_janage) - thisyear)
    return n_start, 1.0 - (payment_janage % 1.0)


def _add_spousal_benefit(spousal_in, i, nd, spousal_amount, fra, yobs, mobs, ages, tobs, thisyear):
    """
    Apply spousal benefit to spousal_in[i, :] starting from the later of both spouses' claim dates.

    The spousal benefit begins when the last spouse has started collecting (since the
    spousal benefit requires the higher-earning spouse to be collecting first), and ends
    at ``nd``, which the caller truncates to the year of the first death: entitlement as a
    spouse ceases then and is replaced by the survivor benefit.
    """
    latest_claim_year = float(np.max(yobs + (mobs - 1) / 12 + ages))
    claim_age = latest_claim_year - yobs[i] - (mobs[i] - 1) / 12
    payment_claim_year = latest_claim_year + 1 / 12
    ns2 = max(0, int(payment_claim_year) - thisyear)
    if ns2 >= nd:
        return  # Spousal benefit would start at or after the end of entitlement.
    spousal_factor = getSpousalFactor(fra, claim_age, bool(tobs[i] == 1))
    spousal_in[i, ns2:nd] += spousal_amount * spousal_factor
    spousal_in[i, ns2] -= spousal_amount * spousal_factor * (payment_claim_year % 1.0)


def validate_survivor_claim_age(survivor_claim_age):
    """
    Normalize and validate a survivor claiming-age setting.

    Accepted values are the keyword ``"immediate"``, the keyword ``"FRA"`` (the survivor's
    full retirement age), or a numeric age in [60, 70]. Keywords are matched
    case-insensitively and returned in canonical form; ages are returned as floats.

    Raises
    ------
    ValueError
        If the value is neither a recognized keyword nor an age in [60, 70].
    """
    if isinstance(survivor_claim_age, str):
        key = survivor_claim_age.strip().lower()
        if key == "immediate":
            return "immediate"
        if key == "fra":
            return "FRA"
        try:
            age = float(key)
        except ValueError:
            raise ValueError(
                f"Unknown survivor_claim_age {survivor_claim_age!r}; expected 'immediate', 'FRA', or an age."
            )
    else:
        age = float(survivor_claim_age)

    if not (60 <= age <= 70):
        raise ValueError(f"survivor_claim_age {age} outside range [60, 70].")
    return age


def _resolve_survivor_claim_age(survivor_claim_age, survivor_fra, age_at_death):
    """
    Return the survivor's age when the survivor benefit begins.

    A survivor benefit cannot start before age 60 nor before the spouse's death, and it
    earns no delayed retirement credits past the survivor full retirement age (FRA), so an
    explicit age beyond that is capped there.
    """
    earliest = max(60.0, float(age_at_death))
    setting = validate_survivor_claim_age(survivor_claim_age)
    if setting == "immediate":
        return earliest
    if setting == "FRA":
        return max(float(survivor_fra), earliest)
    return max(min(setting, float(survivor_fra)), earliest)


class SurvivorStream(NamedTuple):
    """Survivor benefit stream and the parameters it was derived from."""

    survivor_idx: int  # Index of the surviving spouse (-1 if there is no survivor period)
    deceased_idx: int  # Index of the spouse who dies first
    death_year_n: int  # Plan year of the first death (N_n if there is none)
    claim_age: float  # Survivor's age when the survivor benefit begins
    survivor_fra: float  # Survivor full retirement age
    age_at_death: float  # Survivor's age in the year of the first death
    requested_age: object  # The setting as supplied, before clamping (for logging)
    annual: np.ndarray  # Shape (N_n,), annual survivor benefit in today's dollars


def _survivor_period(horizons, N_i, N_n):
    """Return (death_year_n, deceased_idx, survivor_idx); survivor_idx is -1 if no survivor."""
    if N_i == 2 and np.min(horizons) != np.max(horizons):
        death_year_n = int(np.min(horizons))
        deceased_idx = int(np.argmax(horizons == death_year_n))
        return death_year_n, deceased_idx, (deceased_idx + 1) % 2
    return N_n, 0, -1


def survivor_claim_window(yobs, mobs, tobs, end_years):
    """
    Describe the survivor benefit claiming window implied by a set of birth dates and lifespans.

    Intended for callers that hold dates and life expectancies rather than a built plan (the
    Streamlit page, for instance) and need to know which choices are payable before solving.

    Parameters
    ----------
    yobs, mobs, tobs : array-like
        Birth year, month, and day-of-month, one per individual.
    end_years : array-like
        Last calendar year of life, one per individual (birth year + life expectancy).

    Returns
    -------
    dict or None
        ``None`` when there is no survivor period (a single individual, or two lifespans
        ending in the same year). Otherwise the surviving spouse's index, their survivor
        FRA, and the age they reach in the year of the first passing.

        The age at the first passing is the *deterministic* lower end of the window only.
        Under stochastic longevity the death year is redrawn per scenario, so a claiming
        age below it remains meaningful and should be reported rather than forbidden.
    """
    end_years = [int(y) for y in end_years]
    if len(end_years) != 2 or end_years[0] == end_years[1]:
        return None

    deceased_idx = 0 if end_years[0] < end_years[1] else 1
    survivor_idx = 1 - deceased_idx
    survivor_fra = getSurvivorFRAs(
        [yobs[survivor_idx]], [mobs[survivor_idx]], [tobs[survivor_idx]]
    )[0]
    # Owl's convention: the horizon ends after end_years, so the first passing falls in the
    # following plan year -- the same year compute_survivor_stream measures the age against.
    death_year = end_years[deceased_idx] + 1
    return {
        "survivor_idx": survivor_idx,
        "deceased_idx": deceased_idx,
        "survivor_fra": float(survivor_fra),
        "age_at_first_passing": death_year - yobs[survivor_idx] - (mobs[survivor_idx] - 1) / 12,
    }


def compute_survivor_stream(
    pias,
    ages,
    yobs,
    mobs,
    tobs,
    horizons,
    N_i,
    N_n,
    survivor_claim_age="immediate",
    trim_pct=0,
    trim_year=None,
    thisyear=None,
):
    """
    Compute the surviving spouse's survivor benefit as a standalone annual stream.

    The amount follows CFR § 404.338: the greater of the deceased's actual benefit at
    death and 82.5% of their PIA, reduced by ``_survivor_factor`` when claimed before the
    survivor FRA. The start date comes from ``survivor_claim_age`` and is never earlier
    than age 60 or the year of the first death.

    This is the same stream ``compute_social_security_benefits`` combines with the
    survivor's own benefit; it is exposed separately so the SS claiming-age MIP can fold
    it into its own-benefit table (see :func:`apply_survivor_to_benefit_table`).

    Returns
    -------
    SurvivorStream
        With ``survivor_idx == -1`` and an all-zero ``annual`` when there is no survivor
        period (single individual, or both horizons ending together).
    """
    if thisyear is None:
        thisyear = date.today().year

    pias = np.asarray(pias, dtype=np.int32)
    ages = np.asarray(ages, dtype=np.float64)
    death_year_n, deceased_idx, survivor_idx = _survivor_period(horizons, N_i, N_n)

    annual = np.zeros(N_n)
    if survivor_idx < 0 or death_year_n >= N_n:
        return SurvivorStream(-1, deceased_idx, death_year_n, 0.0, 0.0, 0.0, survivor_claim_age, annual)

    survivor_fra = getSurvivorFRAs(
        yobs[survivor_idx : survivor_idx + 1],
        mobs[survivor_idx : survivor_idx + 1],
        tobs[survivor_idx : survivor_idx + 1],
    )[0]
    age_at_death = (thisyear + death_year_n) - yobs[survivor_idx] - (mobs[survivor_idx] - 1) / 12
    claim_age = _resolve_survivor_claim_age(survivor_claim_age, survivor_fra, age_at_death)

    # The deceased's own monthly benefit as of death, unaffected by any partial first year.
    fra_deceased = getFRAs(yobs, mobs, tobs)[deceased_idx]
    started_n, _ = _payment_start(yobs[deceased_idx], mobs[deceased_idx], ages[deceased_idx], thisyear)
    if started_n < death_year_n:
        deceased_monthly = pias[deceased_idx] * getSelfFactor(
            fra_deceased, ages[deceased_idx], bool(tobs[deceased_idx] == 1)
        )
    else:
        deceased_monthly = 0.0  # Died before claiming; only the 82.5% PIA floor applies.

    monthly = max(deceased_monthly, 0.825 * pias[deceased_idx]) * _survivor_factor(survivor_fra, claim_age)

    n_raw, frac = _payment_start(yobs[survivor_idx], mobs[survivor_idx], claim_age, thisyear)
    hs = min(int(horizons[survivor_idx]), N_n)
    if n_raw > death_year_n:
        n_surv, first_frac = n_raw, frac
    else:
        # Entitlement opens with the death; Owl's convention pays the survivor the full death year.
        n_surv, first_frac = death_year_n, 1.0

    if n_surv < hs:
        annual[n_surv:hs] = monthly * 12
        annual[n_surv] *= first_frac

    if trim_pct > 0 and trim_year is not None:
        trim_n = max(0, trim_year - thisyear)
        if trim_n < N_n:
            annual[trim_n:] *= 1.0 - trim_pct / 100

    return SurvivorStream(
        survivor_idx,
        deceased_idx,
        death_year_n,
        claim_age,
        float(survivor_fra),
        float(age_at_death),
        survivor_claim_age,
        annual,
    )


def apply_survivor_to_benefit_table(B_own, survivor, gamma_n):
    """
    Overlay a survivor benefit stream onto the survivor's rows of an own-benefit table.

    For the surviving spouse and every plan year at or after the first death, the entry
    becomes the greater of the own benefit for that candidate claiming age and the
    survivor benefit — exactly what SSA pays. Folding the survivor benefit into the table
    this way makes the post-death payout exact for every candidate claiming age, so the
    SS claiming-age MIP needs no parameter offset after the first death.

    Parameters
    ----------
    B_own : ndarray, shape (N_i, N_K, N_n)
        Own-benefit table from :func:`build_own_benefit_table`, in nominal dollars.
    survivor : SurvivorStream
        From :func:`compute_survivor_stream`; ``annual`` is in today's dollars.
    gamma_n : array, shape (N_n,)
        Cumulative inflation factors, matching those passed to ``build_own_benefit_table``.

    Returns
    -------
    ndarray
        A copy of ``B_own`` with the overlay applied. Returned unchanged (as a copy) when
        there is no survivor period.
    """
    B_eff = np.array(B_own, dtype=float, copy=True)
    if survivor.survivor_idx < 0:
        return B_eff

    nd = survivor.death_year_n
    surv_nominal = survivor.annual[nd:] * gamma_n[nd:]
    B_eff[survivor.survivor_idx, :, nd:] = np.maximum(B_eff[survivor.survivor_idx, :, nd:], surv_nominal)
    return B_eff


def compute_social_security_benefits(
    pias,
    ages,
    yobs,
    mobs,
    tobs,
    horizons,
    N_i,
    N_n,
    trim_pct=0,
    trim_year=None,
    thisyear=None,
    survivor_claim_age="immediate",
):
    """
    Compute annual Social Security benefits by individual and year.

    Benefits are paid in arrears (one month after eligibility). Handles own benefits,
    spousal benefits, survivor benefits, and optional trim. Ages may be adjusted for
    eligibility (e.g. reset to 62 if below).

    Own, spousal, and survivor entitlements are built as three separate streams and then
    combined the way SSA pays them: while both spouses are alive each receives their own
    benefit plus any excess spousal amount; from the year of the first death the survivor
    receives the greater of their own benefit and the survivor benefit, and the spousal
    add-on ends. Because the two post-death streams keep their own start dates, a survivor
    who has not yet claimed does not forfeit their own (still growing) benefit.

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
    survivor_claim_age : str or float
        When the surviving spouse claims the survivor benefit: ``"immediate"`` (default,
        as soon as eligible), ``"FRA"`` (at the survivor FRA), or an explicit age in
        [60, 70]. Never earlier than age 60 or the first death, and capped at the
        survivor FRA since survivor benefits earn no delayed retirement credits.

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
    death_year_n, _, survivor_idx = _survivor_period(horizons, N_i, N_n)

    fras = getFRAs(yobs, mobs, tobs)
    spousalBenefits = getSpousalBenefits(pias)

    own_in = np.zeros((N_i, N_n))
    spousal_in = np.zeros((N_i, N_n))
    for i in range(N_i):
        # Eligibility: born on 1st or 2nd can claim in their birthday month (or prior for 1st).
        # Factor shift: only born on 1st attains age one month early, warranting +1/12 SSA age.
        bornOnFirstDays = tobs[i] <= 2
        bornOnFirst = tobs[i] == 1
        eligible = 62 if bornOnFirstDays else 62 + 1 / 12
        if round(ages[i] * 12) < round(eligible * 12):
            ages[i] = eligible

        payment_start_n, frac = _payment_start(yobs[i], mobs[i], ages[i], thisyear)
        ns = max(0, payment_start_n)
        nd = int(horizons[i])
        own_in[i, ns:nd] = pias[i]
        if payment_start_n >= 0 and ns < nd:
            own_in[i, ns] *= frac

        own_in[i, :] *= getSelfFactor(fras[i], ages[i], bornOnFirst)

        if N_i == 2 and spousalBenefits[i] > 0:
            # Spousal entitlement ends at the first death, when the survivor benefit takes over.
            _add_spousal_benefit(
                spousal_in, i, min(nd, death_year_n), spousalBenefits[i], fras[i], yobs, mobs, ages, tobs, thisyear
            )

    zeta_in = (own_in + spousal_in) * 12

    if trim_pct > 0 and trim_year is not None:
        trim_n = max(0, trim_year - thisyear)
        if trim_n < N_n:
            zeta_in[:, trim_n:] *= 1.0 - trim_pct / 100

    if survivor_idx >= 0 and death_year_n < N_n:
        survivor = compute_survivor_stream(
            pias,
            ages,
            yobs,
            mobs,
            tobs,
            horizons,
            N_i,
            N_n,
            survivor_claim_age=survivor_claim_age,
            trim_pct=trim_pct,
            trim_year=trim_year,
            thisyear=thisyear,
        )
        # SSA pays the greater of the survivor's own benefit and the survivor benefit.
        zeta_in[survivor_idx, death_year_n:] = np.maximum(
            zeta_in[survivor_idx, death_year_n:], survivor.annual[death_year_n:]
        )

    return zeta_in, ages


def build_own_benefit_table(
    pias, fras, yobs, mobs, tobs, horizons, N_i, N_n, gamma_n, trim_pct=0, trim_year=None, N_K=97, thisyear=None
):
    """
    Precompute own-benefit table B_own[N_i, N_K, N_n] for SS claiming-age LP optimization.

    Each entry B_own[i, k, n] is the annual own SS benefit (in nominal, gamma-adjusted dollars)
    that individual i would receive in year n if they claim at ages_k[k].
    Spousal and survivor benefits are NOT included; they are handled as parameters via the SC loop.

    Parameters
    ----------
    pias : array, shape (N_i,)
        Monthly PIAs (Primary Insurance Amounts), one per individual.
    fras : array, shape (N_i,)
        Full retirement ages, one per individual.
    yobs, mobs, tobs : arrays, shape (N_i,)
        Birth year, month, and day-of-month, one per individual.
    horizons : array, shape (N_i,)
        Plan year index when each individual's horizon ends.
    N_i, N_n : int
        Number of individuals and planning years.
    gamma_n : array, shape (N_n,)
        Cumulative inflation factors for plan years 0..N_n-1.
    trim_pct : float
        SS benefit trim percentage (0 = no trim).
    trim_year : int or None
        Calendar year when trim begins (required if trim_pct > 0).
    N_K : int
        Number of claiming-age choices (default 97 = monthly from 62.0 to 70.0 inclusive).
    thisyear : int or None
        Current calendar year (default: date.today().year).

    Returns
    -------
    B_own : ndarray, shape (N_i, N_K, N_n)
        B_own[i, k, n] = annual own-benefit in nominal dollars for individual i claiming at
        ages_k[k] in plan year n. Zero for years before benefit starts or past horizon.
    ages_k : ndarray, shape (N_K,)
        Conventional claiming ages: 62.0, 62+1/12, ..., 70.0.
    """
    if thisyear is None:
        thisyear = date.today().year

    pias = np.asarray(pias, dtype=np.int32)
    fras = np.asarray(fras, dtype=np.float64)

    # Monthly claiming-age grid: 62.0, 62+1/12, ..., 70.0 (97 points over 96 months = 8 years).
    ages_k = 62.0 + np.arange(N_K) / 12.0

    B_own = np.zeros((N_i, N_K, N_n))

    for i in range(N_i):
        if pias[i] == 0:
            continue  # No SS income; B_own[i,:,:] stays zero.
        bornOnFirst = tobs[i] == 1
        bornOnFirstDays = tobs[i] <= 2
        eligible = 62.0 if bornOnFirstDays else 62.0 + 1.0 / 12
        nd = min(int(horizons[i]), N_n)

        for k in range(N_K):
            claim_age = ages_k[k]
            if claim_age < eligible:
                continue  # Ineligible claiming age; skip.

            factor = getSelfFactor(fras[i], claim_age, bornOnFirst)
            benefit_real = pias[i] * 12 * factor  # annual benefit in today's dollars

            # Payment start year (mirrors compute_social_security_benefits logic).
            janage = claim_age + (mobs[i] - 1) / 12
            paymentJanage = janage + 1.0 / 12
            paymentIage = int(paymentJanage)
            payment_start_n = yobs[i] + paymentIage - thisyear
            ns = max(0, payment_start_n)

            if ns >= nd:
                continue  # Payment starts after horizon; no benefit within plan.

            B_own[i, k, ns:nd] = benefit_real * gamma_n[ns:nd]

            # Partial-year adjustment: in year ns, payments cover only the fraction of the
            # year remaining after the first payment month (1 - fractional part of janage).
            if payment_start_n >= 0:
                B_own[i, k, ns] *= 1.0 - (paymentJanage % 1.0)

    if trim_pct > 0 and trim_year is not None:
        trim = 1.0 - trim_pct / 100.0
        trim_n = max(0, trim_year - thisyear)
        if 0 <= trim_n < N_n:
            B_own[:, :, trim_n:] *= trim

    return B_own, ages_k
