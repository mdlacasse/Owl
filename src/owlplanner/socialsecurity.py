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

- Earnings test: the rules are implemented below (``earnings_test`` and its helpers:
  exempt amounts, excess, family charging, grace year, ARF) and applied to the plan's
  streams by ``Plan._ss_streams`` in every solve; where it withholds nothing the plan
  keeps ``compute_social_security_benefits``' streams. Assumptions of the rule
  implementation: earnings
  are spread evenly over ``months worked``; exempt amounts after the last published year (2027)
  are held at its real level (statute indexes them to wages with a two-year lag); years before
  the plan have no earnings (so anyone entitled before the plan has used their grace
  year); the test is not applied to checks paid from the year of the first death on
  (survivor benefits under the test and the survivor ARF are not modeled),
  but the survivor benefit does start from the deceased's benefit after their ARF.

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
compute_survivor_stream, validate_survivor_claim_age.
All other functions are internal and may change without notice.
"""

__all__ = [
    "getFRAs",
    "getSurvivorFRAs",
    "compute_social_security_benefits",
    "compute_survivor_stream",
    "survivor_claim_window",
    "validate_survivor_claim_age",
    "ExemptAmounts",
    "get_exempt_amounts",
    "plan_exempt_for_year",
    "excess_earnings",
    "countable_earnings",
    "is_non_service_month",
    "initial_grace_year",
    "charge_excess_months",
    "arf_self_factor",
    "arf_spousal_factor",
    "earnings_test",
    "EarningsTestResult",
]

import math
import numpy as np
from datetime import date
from typing import Callable, NamedTuple, Optional, Sequence

from . import utils as u

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


def _survivor_factor(survivor_fra, survivor_age, bornOnFirstDays=False):
    """
    Return the benefit factor for a survivor claiming before their survivor FRA.

    Per SSA rules, a survivor claiming between age 60 and their survivor FRA receives a
    reduced benefit, linearly interpolated from 100% at survivor FRA down to 71.5% at 60:
    the months of entitlement before survivor FRA times .285, over the months from age 60 to
    survivor FRA (20 CFR 404.410(c)(1)). At or above survivor FRA the factor is 1.0. Survivor
    benefits cannot be claimed before age 60; earlier ages are clamped to 60.

    A survivor born on the 1st attains every age in the month before (20 CFR 404.102), so the
    months are counted on the SSA age, one month more than the conventional age (#212): at a
    conventional 60 they are 83 months before an FRA of 67, not 84, and they reach 60 at a
    conventional 59 years 11 months, where the factor is 71.5%.

    Parameters
    ----------
    survivor_fra : float
        Survivor full retirement age in fractional years.
    survivor_age : float
        Survivor's conventional age (fractional years) when the survivor benefit begins.
        An SSA age below 60 is treated as 60.
    bornOnFirstDays : bool, optional
        True if the survivor was born on the 1st of a month (see _ssa_age).
    """
    survivor_age = max(_ssa_age(survivor_age, bornOnFirstDays), 60)  # No survivor benefits before 60
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

    # Delayed credits end with the month before age 70 is attained (42 U.S.C. 402(w)(2)(A);
    # POMS RS 00615.690): someone born on the 1st attains 70 a month before their conventional 70,
    # so their SSA age is capped there and a claim at a conventional 70 gets no extra credit (#212).
    diff = fra - min(_ssa_age(convage, bornOnFirstDays), 70)
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


def _add_spousal_benefit(spousal_in, i, nd, spousal_amount, fra, yobs, mobs, ages, tobs, thisyear, own_drc=0.0):
    """
    Apply spousal benefit to spousal_in[i, :] starting from the later of both spouses' claim dates.

    The spousal benefit begins when the last spouse has started collecting (since the
    spousal benefit requires the higher-earning spouse to be collecting first), and ends
    at ``nd``, which the caller truncates to the year of the first death: entitlement as a
    spouse ceases then and is replaced by the survivor benefit.

    ``own_drc`` is the monthly amount of delayed retirement credits in individual i's own benefit.
    The combined payment is computed without them, and the own benefit with them is subtracted
    from it to give the spousal payment (POMS RS 00615.694; 42 U.S.C. 402(k)(3)(A)), so the credits
    come out of the spousal excess, down to zero, rather than add to it (#211). An own benefit with
    credits was claimed after FRA, so the spousal start, the later of the two claims, is too, and
    its factor is 1.
    """
    latest_claim_year = float(np.max(yobs + (mobs - 1) / 12 + ages))
    claim_age = latest_claim_year - yobs[i] - (mobs[i] - 1) / 12
    payment_claim_year = latest_claim_year + 1 / 12
    payment_start_n = int(payment_claim_year) - thisyear
    ns2 = max(0, payment_start_n)
    if ns2 >= nd:
        return  # Spousal benefit would start at or after the end of entitlement.
    spousal_factor = getSpousalFactor(fra, claim_age, bool(tobs[i] == 1))
    monthly = max(0.0, spousal_amount * spousal_factor - own_drc)
    spousal_in[i, ns2:nd] += monthly
    if payment_start_n >= 0:
        # Partial first year only when the first spousal check falls inside the plan.
        spousal_in[i, ns2] -= monthly * (payment_claim_year % 1.0)


def validate_survivor_claim_age(survivor_claim_age):
    """
    Normalize and validate a survivor claiming-age setting.

    Accepted values are the keyword ``"immediate"``, the keyword ``"FRA"`` (the survivor's
    full retirement age), or a numeric age in [59 11/12, 70]: a survivor born on the 1st reaches
    60 at a conventional 59 years 11 months, and anyone else's earlier age is raised to 60 when
    resolved (_resolve_survivor_claim_age). Keywords are matched case-insensitively and returned
    in canonical form; ages are returned as floats.

    Raises
    ------
    ValueError
        If the value is neither a recognized keyword nor an age in [59 11/12, 70].
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
            ) from None
    else:
        age = float(survivor_claim_age)

    if not (60 - 1 / 12 - 1e-9 <= age <= 70):
        raise ValueError(f"survivor_claim_age {age} outside range [59 11/12, 70].")
    return age


def survivor_claim_limits(survivor_fra, bornOnFirstDays=False):
    """
    Return (earliest, full_rate) conventional ages for claiming a survivor benefit.

    The benefit can start at age 60 and reaches its full rate at the survivor FRA. Someone born on
    the 1st attains both a month earlier than their conventional age (20 CFR 404.102): 59 years
    11 months, and the survivor FRA minus one month.
    """
    shift = 1 / 12 if bornOnFirstDays else 0.0
    return 60.0 - shift, float(survivor_fra) - shift


def _resolve_survivor_claim_age(survivor_claim_age, survivor_fra, age_at_death, bornOnFirstDays=False):
    """
    Return the survivor's conventional age when the survivor benefit begins.

    A survivor benefit cannot start before age 60 nor before the spouse's death, and it
    earns no delayed retirement credits past the survivor full retirement age (FRA), so an
    explicit age beyond that is capped there and "FRA" claims there. For a survivor born on the
    1st both ages come a month earlier (survivor_claim_limits): "FRA" claims at the conventional
    survivor FRA minus one month, which is already the full rate.
    """
    earliest, full_rate = survivor_claim_limits(survivor_fra, bornOnFirstDays)
    earliest = max(earliest, float(age_at_death))
    setting = validate_survivor_claim_age(survivor_claim_age)
    if setting == "immediate":
        return earliest
    if setting == "FRA":
        return max(full_rate, earliest)
    return max(min(setting, full_rate), earliest)


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
    born_first: bool = False  # Survivor born on the 1st: ages attained a month early (survivor_claim_limits)


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
    earliest, full_rate = survivor_claim_limits(survivor_fra, int(tobs[survivor_idx]) == 1)
    return {
        "survivor_idx": survivor_idx,
        "deceased_idx": deceased_idx,
        "survivor_fra": float(survivor_fra),
        "earliest_age": earliest,  # conventional ages: a month earlier for those born on the 1st
        "full_rate_age": full_rate,
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
    deceased_factor=None,
):
    """
    Compute the surviving spouse's survivor benefit as a standalone annual stream.

    The amount follows Social Security Act 202(e)(2) (42 U.S.C. 402(e)(2)) and CFR § 404.338:
    the deceased's PIA, plus any delayed retirement credits, reduced by ``_survivor_factor``
    when claimed before the survivor FRA (subsection (q)). If the deceased had claimed a reduced
    benefit, the result is then capped at the greater of that benefit and 82.5% of the PIA:
    the widow(er)'s limit applies "after application of subsection (q)" (202(e)(2)(D);
    POMS RS 00615.320 A.3), so it caps the age-reduced benefit and is not itself reduced (#210).
    A deceased who had not claimed leaves the full PIA, plus the delayed retirement credits
    earned up to death, with no limit.
    The start date comes from ``survivor_claim_age`` and is never earlier than age 60 or the
    year of the first death.

    This is the same stream ``compute_social_security_benefits`` combines with the
    survivor's own benefit; it is exposed separately so callers can report it on its own.

    ``deceased_factor`` replaces the deceased's own-benefit factor when
    they had claimed, e.g. after an earnings-test ARF raised it (``earnings_test``).

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
    survivor_first = bool(tobs[survivor_idx] == 1)  # SSA age one month ahead (#212)
    claim_age = _resolve_survivor_claim_age(survivor_claim_age, survivor_fra, age_at_death, survivor_first)

    # The deceased's own monthly benefit as of death, unaffected by any partial first year.
    fra_deceased = getFRAs(yobs, mobs, tobs)[deceased_idx]
    started_n, _ = _payment_start(yobs[deceased_idx], mobs[deceased_idx], ages[deceased_idx], thisyear)
    if started_n < death_year_n:
        factor = deceased_factor
        if factor is None:
            factor = getSelfFactor(fra_deceased, ages[deceased_idx], bool(tobs[deceased_idx] == 1))
        # PIA, plus delayed retirement credits when claimed after FRA.
        monthly = pias[deceased_idx] * max(1.0, factor) * _survivor_factor(survivor_fra, claim_age, survivor_first)
        if factor < 1.0:
            # Widow(er)'s limit, after the age reduction (SSA 202(e)(2)(D), #210).
            monthly = min(monthly, max(pias[deceased_idx] * factor, 0.825 * pias[deceased_idx]))
    else:
        # Died before claiming: no reduced benefit, so the widow(er)'s limit (82.5% floor) does not
        # apply (POMS RS 00615.320). The survivor's base is the full PIA, plus the delayed retirement
        # credits earned up to death when death came after FRA (capped at 70).
        age_at_death_dec = (thisyear + death_year_n) - yobs[deceased_idx] - (mobs[deceased_idx] - 1) / 12
        base = pias[deceased_idx] * max(
            1.0,
            getSelfFactor(fra_deceased, min(70.0, max(62.0, age_at_death_dec)), bool(tobs[deceased_idx] == 1)),
        )
        monthly = base * _survivor_factor(survivor_fra, claim_age, survivor_first)

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
        survivor_first,
    )


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
        [60, 70] (59 11/12 for a survivor born on the 1st). Never earlier than age 60 or the
        first death, and capped at the survivor FRA since survivor benefits earn no delayed
        retirement credits; both ages are a month earlier for a survivor born on the 1st.

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

    # Eligibility: born on 1st or 2nd can claim in their birthday month (or prior for 1st).
    # Every age is reset before any stream is built: the spousal start reads both ages.
    for i in range(N_i):
        bornOnFirstDays = tobs[i] <= 2
        eligible = 62 if bornOnFirstDays else 62 + 1 / 12
        if round(ages[i] * 12) < round(eligible * 12):
            ages[i] = eligible

    own_in = np.zeros((N_i, N_n))
    spousal_in = np.zeros((N_i, N_n))
    for i in range(N_i):
        # Factor shift: only born on 1st attains age one month early, warranting +1/12 SSA age.
        bornOnFirst = tobs[i] == 1

        payment_start_n, frac = _payment_start(yobs[i], mobs[i], ages[i], thisyear)
        ns = max(0, payment_start_n)
        nd = int(horizons[i])
        own_in[i, ns:nd] = pias[i]
        if payment_start_n >= 0 and ns < nd:
            own_in[i, ns] *= frac

        self_factor = getSelfFactor(fras[i], ages[i], bornOnFirst)
        own_in[i, :] *= self_factor

        if N_i == 2 and spousalBenefits[i] > 0:
            # Spousal entitlement ends at the first death, when the survivor benefit takes over.
            # Delayed credits in the own benefit come out of the spousal excess (#211).
            own_drc = pias[i] * max(0.0, self_factor - 1.0)
            _add_spousal_benefit(
                spousal_in, i, min(nd, death_year_n), spousalBenefits[i], fras[i], yobs, mobs, ages, tobs, thisyear,
                own_drc,
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


# --------------------------------------------------------------------------------------
# SSA earnings test. Pure rules; Plan._ss_streams applies them to
# the plan's streams in every solve.
#
# Primary sources (read 2026-10-17/18):
#   RS 02501.025 D  annual / monthly exempt amounts (TN 55, 11/21/2025)
#   RS 02501.021 B  what earnings count; FRA-year months before the FRA month
#   RS 02501.030    monthly test / initial grace year / non-service months
#   RS 02501.080    excess = (earnings - exempt) / 2, or / 3 in the FRA year, floored
#   RS 02501.095    charging: worker's excess to the family; aux's own excess to the aux
#   RS 02501.110    partial last month split in proportion to original benefit shares
#   RS 00615.480/.482/.490  ARF: subtract crediting months from the reduction factor
#   20 CFR 404.430, 404.434, 404.435  indexing, charging, grace year
#
# Earnings are inputs, so for a given claiming month everything the test does is a
# fixed function of that month: no LP piece here.
# --------------------------------------------------------------------------------------

# POMS RS 02501.025 D (TN 55, 11/21/2025); 2027 from SSA's notice of 10/26/2026, 91 FR
# 67380. Annual amounts, each year's nominal dollars; monthly = annual / 12. A plan reads
# them in its own dollars through plan_exempt_for_year. After the last known year they are
# held at that level in real terms (statute indexes them to wages with a two-year lag,
# 404.430(a)(2); Owl has no wage index, so this slightly overstates withholding later on).
_EXEMPT_TABLE = {
    2024: (22_320.0, 59_520.0),
    2025: (23_400.0, 62_160.0),
    2026: (24_480.0, 65_160.0),
    2027: (25_560.0, 67_920.0),
}
_EXEMPT_TABLE_FIRST_YEAR = min(_EXEMPT_TABLE)
_EXEMPT_TABLE_LAST_YEAR = max(_EXEMPT_TABLE)


class ExemptAmounts(NamedTuple):
    """Annual earnings-test exempt amounts for one year, in the caller's dollars."""

    annual: float
    """Under FRA for the whole year (RS 02501.025 D)."""

    annual_fra: float
    """In the year of FRA attainment (only months before the FRA month count)."""

    @property
    def monthly(self) -> float:
        return self.annual / 12.0

    @property
    def monthly_fra(self) -> float:
        return self.annual_fra / 12.0


def get_exempt_amounts(year: int, table: Optional[dict] = None) -> ExemptAmounts:
    """
    Return the earnings-test exempt amounts for ``year`` in that year's nominal dollars.

    Years present in ``table`` (default: the published 2024-2027 amounts) use those
    amounts. Later years hold the last known nominal amount, a floor; earlier years
    use the first known amount (tests only). A plan, whose earnings are in its first
    year's dollars, reads them through :func:`plan_exempt_for_year` instead.
    """
    tbl = _EXEMPT_TABLE if table is None else table
    if year in tbl:
        annual, annual_fra = tbl[year]
    elif year > max(tbl):
        annual, annual_fra = tbl[max(tbl)]
    else:
        annual, annual_fra = tbl[min(tbl)]
    return ExemptAmounts(float(annual), float(annual_fra))


def plan_exempt_for_year(year0, gamma_n, N_n, table=None) -> Callable[[int], ExemptAmounts]:
    """
    Return ``year -> ExemptAmounts`` for a plan whose dollars are those of ``year0``,
    with inflation factors ``gamma_n`` (1 in ``year0``).

    A plan year in the table takes its nominal amount deflated by that year's factor, so
    a published amount is not inflated a second time; a later one holds the last amount
    flat in real terms (u.nominal_by_year). Years outside the plan, which the grace-year
    scan reads without earnings, take the nominal amount (:func:`get_exempt_amounts`).
    """
    tbl = _EXEMPT_TABLE if table is None else table
    gamma = np.asarray(gamma_n, dtype=float)[:N_n]
    plan_amounts = u.nominal_by_year(tbl, year0, gamma, N_n) / gamma[:, None]

    def exempt_for_year(year):
        n = int(year) - int(year0)
        if 0 <= n < N_n:
            return ExemptAmounts(float(plan_amounts[n, 0]), float(plan_amounts[n, 1]))
        return get_exempt_amounts(year, tbl)

    return exempt_for_year


def exempt_table_last_year() -> int:
    """The last year whose exempt amounts are published in the table."""
    return _EXEMPT_TABLE_LAST_YEAR


def countable_earnings(
    earnings: float,
    months_worked: int,
    is_fra_year: bool,
    fra_month_in_year: int,
) -> float:
    """
    Return the earnings that count for the test in one calendar year (RS 02501.021 B).

    Below the FRA year the whole year's earnings count. In the FRA year only the
    months before the FRA month count. Earnings are taken as spread evenly over
    ``months_worked`` months at the start of the year.
    """
    if earnings <= 0 or months_worked <= 0:
        return 0.0
    if not is_fra_year:
        return float(earnings)
    months_before = min(months_worked, max(0, fra_month_in_year - 1))
    return float(earnings) * months_before / months_worked


def excess_earnings(countable: float, exempt_annual: float, is_fra_year: bool) -> int:
    """
    Return excess earnings for the year, rounded down to the dollar (RS 02501.080).

    Under FRA: $1 withheld per $2 over the exempt amount. In the FRA year:
    $1 per $3 over the (higher) exempt amount. Never negative.
    """
    divisor = 3.0 if is_fra_year else 2.0
    return int(math.floor(max(0.0, (float(countable) - float(exempt_annual)) / divisor)))


def is_non_service_month(
    month_in_year: int,
    year_earnings: float,
    months_worked: int,
    monthly_exempt: float,
) -> bool:
    """
    Return whether a month of entitlement before FRA is a non-service month (404.435(a)(7)).

    A month with no work, or with wages at or below the monthly exempt amount, is a
    non-service month. Substantial services in self-employment are out of scope (the
    monthly test here is only the grace-year rule). ``months_worked`` are at the start
    of the year; earnings are spread evenly over them.
    """
    if months_worked <= 0 or year_earnings <= 0:
        return True  # no work that month
    if month_in_year > months_worked:
        return True  # after the months-worked period
    return (year_earnings / months_worked) <= monthly_exempt


def initial_grace_year(
    earnings_by_year: dict,
    ent_start_month_in_year: int,
    start_year: int,
    exempt_for_year: Callable[[int], ExemptAmounts],
    months_worked_by_year: Optional[dict] = None,
    end_year: Optional[int] = None,
    fra_year: Optional[int] = None,
    fra_month_in_year: Optional[int] = None,
) -> Optional[int]:
    """
    Return the initial grace year, or None (404.435(b)).

    The initial grace year is the first taxable year with a non-service month in or
    after the month of entitlement and before the month of FRA (RS 02501.030). A year
    with no earnings has non-service months in every entitlement month and can be the
    grace year (using it up); a later year then gets the annual test only. Only one
    initial grace year. Scans years ``start_year`` .. ``end_year`` (default: the last
    year in ``earnings_by_year``). A year missing from ``earnings_by_year`` (one before
    the plan, say) counts as a year without earnings.

    In ``fra_year`` only months before ``fra_month_in_year`` count, and the monthly
    exempt amount is 1/12 of the FRA-year annual amount (RS 02501.025 B.2: 1/12 of the
    *applicable* annual amount).
    """
    months_worked_by_year = months_worked_by_year or {}
    if end_year is None:
        end_year = max(earnings_by_year) if earnings_by_year else start_year
    for year in range(start_year, int(end_year) + 1):
        y_earn = float(earnings_by_year.get(year, 0.0))
        n_work = int(months_worked_by_year.get(year, 12 if y_earn > 0 else 0))
        exempt = exempt_for_year(year)
        in_fra_year = fra_year is not None and year == fra_year
        monthly = exempt.monthly_fra if in_fra_year else exempt.monthly
        last_month = fra_month_in_year - 1 if in_fra_year and fra_month_in_year is not None else 12
        ent_month0 = ent_start_month_in_year if year == start_year else 1
        for month_num in range(ent_month0, last_month + 1):
            if is_non_service_month(month_num, y_earn, n_work, monthly):
                return year
    return None


def charge_excess_months(
    monthly: Sequence[Sequence[float]],
    excess: float,
    shares: Optional[Sequence[float]] = None,
    start: int = 0,
) -> tuple:
    """
    Charge excess against a family's monthly benefits (RS 02501.095, RS 02501.110).

    Parameters
    ----------
    monthly
        ``monthly[bene][month]``: benefit payable to each beneficiary in each month
        of the period being charged, before this year's work deductions. Mutated in
        place to the paid amount.
    excess
        Whole-dollar excess to charge (already floored by :func:`excess_earnings`).
    shares
        Original entitlement shares used to split a partial month (RS 02501.110:
        before family-max and early-entitlement reductions). Default: the month's
        pre-deduction amounts. A share larger than the beneficiary's rate is capped
        there and the excess reapportioned (Example 3 there).
    start
        First month index to charge (first month of entitlement in the year).

    Returns
    -------
    withheld : list of lists
        ``withheld[bene][month]``.
    months_with_deduction : int
        Number of months with any deduction (crediting months for the ARF; a partial
        deduction counts).
    partial_index : int or None
        Month index where the excess ran out and a partial benefit was paid.
    """
    if not monthly or not monthly[0]:
        return [[] for _ in monthly], 0, None
    n_bene = len(monthly)
    n_months = len(monthly[0])
    withheld = [[0.0] * n_months for _ in range(n_bene)]
    months_with_deduction = 0
    partial_index = None
    remaining = float(excess)
    if shares is not None:
        shares = [float(s) for s in shares]
        if len(shares) != n_bene:
            raise ValueError("shares length must match number of beneficiaries")

    for m in range(start, n_months):
        if remaining <= 0:
            break
        family = sum(monthly[b][m] for b in range(n_bene))
        if family <= 0:
            continue
        take = min(remaining, family)
        if take >= family - 1e-9:
            # Full month withheld from everyone.
            for b in range(n_bene):
                withheld[b][m] = monthly[b][m]
                monthly[b][m] = 0.0
            months_with_deduction += 1
            remaining -= family
        else:
            # Partial month: pay the family the remainder, split by original shares
            # (RS 02501.110). Cap each share at the beneficiary's rate and reapportion.
            paid_family = family - take
            rates = [monthly[b][m] for b in range(n_bene)]
            if shares is None:
                use_shares = [r if r > 0 else 0.0 for r in rates]
            else:
                use_shares = list(shares)
            total_share = sum(use_shares)
            if total_share <= 0:
                use_shares = list(rates)
                total_share = sum(use_shares)
            pay = [0.0] * n_bene
            unpaid = paid_family
            active = [b for b in range(n_bene) if rates[b] > 0]
            # Iterative cap-and-reapportion (RS 02501.110 B.2).
            for _ in range(n_bene + 1):
                if not active or unpaid <= 1e-9:
                    break
                wsum = sum(use_shares[b] for b in active)
                if wsum <= 0:
                    break
                overflow = 0.0
                still = []
                for b in active:
                    offer = unpaid * use_shares[b] / wsum
                    if pay[b] + offer > rates[b] + 1e-9:
                        overflow += pay[b] + offer - rates[b]
                        pay[b] = rates[b]
                    else:
                        pay[b] += offer
                        still.append(b)
                if overflow <= 1e-9:
                    unpaid = 0.0
                    break
                unpaid = overflow
                active = still
            for b in range(n_bene):
                withheld[b][m] = monthly[b][m] - pay[b]
                monthly[b][m] = pay[b]
            months_with_deduction += 1
            partial_index = m
            remaining -= take
            break
    return withheld, months_with_deduction, partial_index


def _fra_conventional_age(fra: float, born_on_first: bool) -> float:
    """
    Conventional age at which the SSA age reaches ``fra``.

    Someone born on the 1st attains each age a month early (RS 00615.015; ``_ssa_age``),
    so their FRA falls one calendar month before the conventional age ``fra``.
    """
    return float(fra) - (1.0 / 12 if born_on_first else 0.0)


def _arf_effective_age(fra: float, claim_age: float, crediting_months: int, born_on_first: bool) -> float:
    """Conventional claiming age whose reduction equals the one left after the ARF (capped at FRA)."""
    return min(_fra_conventional_age(fra, born_on_first), float(claim_age) + crediting_months / 12.0)


def arf_self_factor(fra: float, claim_age: float, crediting_months: int, born_on_first: bool = False) -> float:
    """
    Own-benefit factor after the adjustment of the reduction factor (RS 00615.480/.482/.490).

    Crediting months (months of full or partial work deduction) are subtracted from
    the original reduction factor, which is the same as recomputing at
    ``claim_age + crediting_months/12``, capped at FRA (for someone born on the 1st,
    a month before the conventional age ``fra``), so the factor never exceeds 1.
    Effective with the month of FRA. This follows the RS 00615.490 procedure ("Determine
    crediting months. Subtract from original reduction factor. Apply result to PIA"),
    which has no numeric example.
    """
    if crediting_months <= 0 or claim_age >= _fra_conventional_age(fra, born_on_first):
        return getSelfFactor(fra, claim_age, born_on_first)
    return min(1.0, getSelfFactor(fra, _arf_effective_age(fra, claim_age, crediting_months, born_on_first),
                                  born_on_first))


def arf_spousal_factor(fra: float, claim_age: float, crediting_months: int, born_on_first: bool = False) -> float:
    """
    Spousal-benefit factor after the ARF. Same crediting-month rule as own benefits
    (RS 00615.482 B.2: a spouse is credited for deductions from their own work and
    from the worker's). No delayed credit past FRA.
    """
    if crediting_months <= 0 or claim_age >= _fra_conventional_age(fra, born_on_first):
        return getSpousalFactor(fra, claim_age, born_on_first)
    return min(1.0, getSpousalFactor(fra, _arf_effective_age(fra, claim_age, crediting_months, born_on_first),
                                     born_on_first))


class EarningsTestResult(NamedTuple):
    """Streams after the earnings test (payment-year annual amounts, today's dollars)."""

    zeta_in: np.ndarray
    """Shape (N_i, N_n); annual benefits paid, one month in arrears."""

    withheld_in: np.ndarray
    """Shape (N_i, N_n); amounts withheld by the test, same bucketing."""

    arf_months: np.ndarray
    """Shape (N_i,); crediting months on each person's own record, applied at FRA."""

    ages: np.ndarray
    """Claiming ages after the eligibility reset (62 or 62+1/12)."""

    excess_by_year: np.ndarray
    """Shape (N_i, n_years); excess for each calendar year (0 at/after the FRA year)."""

    arf_months_spousal: np.ndarray
    """Shape (N_i,); crediting months on each person's spouse record (their spousal
    add-on), applied at their FRA. ARFs are granted separately on each record
    (RS 00615.482 B.3, NOTE)."""


def _ent_start_abs(yob: int, mob: int, claim_age: float) -> int:
    """Absolute month (year*12 + month-1) when entitlement begins (age attained)."""
    return int(yob) * 12 + (int(mob) - 1) + int(round(float(claim_age) * 12))


def _chargeable_months(start_abs, end_abs, ent_abs, fra_abs, y_earn, months_worked, monthly_exempt, is_grace):
    """
    Absolute months in [start_abs, end_abs) that the annual test may charge: months of
    entitlement before FRA, less the non-service months of the grace year.
    ``monthly_exempt`` is the year's applicable monthly amount (RS 02501.025 B.2).
    """
    months = []
    for abs_m in range(max(start_abs, ent_abs), min(end_abs, fra_abs)):
        month_num = abs_m % 12 + 1
        if is_grace and is_non_service_month(month_num, y_earn, months_worked, monthly_exempt):
            continue
        months.append(abs_m)
    return months


def earnings_test(
    pias,
    ages,
    yobs,
    mobs,
    tobs,
    horizons,
    N_i,
    N_n,
    earnings_in,
    work_months_in=None,
    exempt_for_year=None,
    thisyear=None,
    trim_pct=0,
    trim_year=None,
    survivor_claim_age="immediate",
):
    """
    Apply the SSA earnings test to one- or two-person SS streams.

    Builds the same monthly entitlement streams as ``compute_social_security_benefits``
    (own + spousal add-on from the later claim), charges, year by year, each worker's
    excess against the family benefit on their record first and then each auxiliary's
    own excess against their remaining benefit (RS 02501.095), applies the ARF from each
    person's FRA with crediting months counted separately on each record (RS 00615.482
    B.3, NOTE), and aggregates to annual payment-year amounts. With zero earnings the
    result equals ``compute_social_security_benefits``.

    Survivor period: from the first death the survivor receives the greater of their
    own benefit and the survivor benefit, as in ``compute_social_security_benefits``.
    The survivor benefit is based on the deceased's benefit after their ARF when the
    death comes after the deceased's FRA. The test is **not** applied to checks paid
    from the year of the first death on (survivor benefits under the test, and the
    survivor ARF of RS 00615.580, are not modeled).

    Years before the plan carry no earnings here, so a person entitled before the plan
    has their initial grace year in their (pre-plan) entitlement year and only the
    annual test in plan years.

    Parameters match ``compute_social_security_benefits``, plus:
    earnings_in : array, shape (N_i, N_n)
        Annual countable earnings (W-2 box 5 + net SE) by plan year, in today's dollars
        like the exempt amounts (the HFP column is nominal: deflate it first).
    work_months_in : array or None
        Shape (N_i, N_n); months of work at the start of each year. 0 (or None for the
        whole array) means "not given": 12 when that year's earnings are positive, else 0.
    exempt_for_year : callable or None
        ``year -> ExemptAmounts``. Default: :func:`get_exempt_amounts`.

    Returns
    -------
    EarningsTestResult
    """
    if thisyear is None:
        thisyear = date.today().year
    if exempt_for_year is None:
        exempt_for_year = get_exempt_amounts

    pias = np.asarray(pias, dtype=np.int32)
    ages = np.asarray(ages, dtype=np.float64).copy()
    yobs = np.asarray(yobs, dtype=np.int64)
    mobs = np.asarray(mobs, dtype=np.int64)
    tobs = np.asarray(tobs, dtype=np.int64)
    horizons = np.asarray(horizons, dtype=np.int64)
    earnings_in = np.asarray(earnings_in, dtype=np.float64)
    if earnings_in.shape != (N_i, N_n):
        raise ValueError(f"earnings_in shape {earnings_in.shape} != ({N_i}, {N_n})")
    if work_months_in is None:
        work_months_in = np.zeros((N_i, N_n))
    work_months_in = np.asarray(work_months_in)
    if work_months_in.shape != (N_i, N_n):
        raise ValueError(f"work_months_in shape {work_months_in.shape} != ({N_i}, {N_n})")
    # Earnings over zero months of work would count for nothing (countable_earnings).
    work_months_in = np.where((work_months_in <= 0) & (earnings_in > 0), 12, work_months_in)

    death_year_n, deceased_idx, survivor_idx = _survivor_period(horizons, N_i, N_n)
    fras = getFRAs(yobs, mobs, tobs)
    spousalBenefits = getSpousalBenefits(pias)
    born_on_first = [bool(tobs[i] == 1) for i in range(N_i)]

    # Eligibility reset (same rule as compute_social_security_benefits).
    for i in range(N_i):
        bornOnFirstDays = tobs[i] <= 2
        eligible = 62.0 if bornOnFirstDays else 62.0 + 1.0 / 12
        if round(ages[i] * 12) < round(eligible * 12):
            ages[i] = eligible

    # --- Monthly entitlement grids on absolute months, pre-ARF -------------------
    # The grid starts with the December before the plan: its check is paid in January
    # of the first plan year (payments one month in arrears). Absolute month a sits at
    # index a - g0. ARF is effective only from the FRA month and charging never reaches
    # that month, so crediting months are a function of the pre-ARF stream alone.
    g0 = thisyear * 12 - 1
    M = N_n * 12 + 1
    own = np.zeros((N_i, M))
    spousal = np.zeros((N_i, M))
    ent_abs = [0] * N_i
    fra_abs = [0] * N_i
    spousal_age = [0.0] * N_i

    for i in range(N_i):
        ent_abs[i] = _ent_start_abs(yobs[i], mobs[i], ages[i])
        fra_abs[i] = _ent_start_abs(yobs[i], mobs[i], _fra_conventional_age(fras[i], born_on_first[i]))
        # horizons[i] is Owl's exclusive end plan year; entitlement runs through December
        # of the year before it, whose check (paid in January) is then dropped below.
        end_abs = (thisyear + min(int(horizons[i]), N_n)) * 12
        lo = max(ent_abs[i], g0)
        if lo < end_abs:
            own[i, lo - g0 : end_abs - g0] = float(pias[i]) * getSelfFactor(
                float(fras[i]), float(ages[i]), born_on_first[i]
            )

    latest = max(ent_abs)
    if N_i == 2:
        for i in range(N_i):
            if spousalBenefits[i] <= 0:
                continue
            spousal_age[i] = max(62.0, (latest - (int(yobs[i]) * 12 + int(mobs[i]) - 1)) / 12.0)
            # Spousal entitlement ends at the first death (_add_spousal_benefit's rule).
            end_abs = (thisyear + min(int(horizons[i]), N_n, death_year_n)) * 12
            lo = max(latest, g0)
            if lo < end_abs:
                factor = getSpousalFactor(float(fras[i]), spousal_age[i], born_on_first[i])
                # Delayed credits in the own benefit come out of the spousal excess (#211,
                # _add_spousal_benefit's rule). Credits mean a claim after FRA, outside the test.
                self_factor = getSelfFactor(float(fras[i]), float(ages[i]), born_on_first[i])
                own_drc = float(pias[i]) * max(0.0, self_factor - 1.0)
                spousal[i, lo - g0 : end_abs - g0] = max(0.0, float(spousalBenefits[i]) * factor - own_drc)

    # --- Excess per person per calendar year ------------------------------------
    excess_by_year = np.zeros((N_i, N_n))
    grace = [None] * N_i
    fra_year = [fra_abs[i] // 12 for i in range(N_i)]
    fra_month = [fra_abs[i] % 12 + 1 for i in range(N_i)]

    for i in range(N_i):
        ent_year = ent_abs[i] // 12
        earn_map = {thisyear + n: float(earnings_in[i, n]) for n in range(N_n)}
        months_map = {thisyear + n: int(work_months_in[i, n]) for n in range(N_n)}
        grace[i] = initial_grace_year(
            earn_map,
            ent_abs[i] % 12 + 1,
            ent_year,
            exempt_for_year,
            months_map,
            end_year=fra_year[i],
            fra_year=fra_year[i],
            fra_month_in_year=fra_month[i],
        )
        for n in range(N_n):
            y = thisyear + n
            if y < ent_year or y > fra_year[i]:
                continue
            is_fra_year = y == fra_year[i]
            exempt = exempt_for_year(y)
            countable = countable_earnings(
                earn_map[y], months_map[y], is_fra_year, fra_month[i] if is_fra_year else 13
            )
            excess_by_year[i, n] = excess_earnings(
                countable, exempt.annual_fra if is_fra_year else exempt.annual, is_fra_year
            )

    # --- Charge ----------------------------------------------------------------
    # Checks paid from the year of the first death on are not charged (docstring).
    survivor_stop = (thisyear + death_year_n) * 12 - 1 if survivor_idx >= 0 and death_year_n < N_n else None

    def _year_months(i, n):
        y = thisyear + n
        if y < ent_abs[i] // 12 or y > fra_year[i]:
            return []
        end_abs = (y + 1) * 12
        if i == survivor_idx and survivor_stop is not None:
            end_abs = min(end_abs, survivor_stop)
        exempt = exempt_for_year(y)
        monthly_exempt = exempt.monthly_fra if y == fra_year[i] else exempt.monthly
        return _chargeable_months(
            y * 12,
            end_abs,
            ent_abs[i],
            fra_abs[i],
            float(earnings_in[i, n]),
            int(work_months_in[i, n]),
            monthly_exempt,
            grace[i] == y,
        )

    # j is an auxiliary on i's record when j receives a spousal add-on (paid on i).
    aux_on = {}
    if N_i == 2:
        for i in range(N_i):
            j = (i + 1) % 2
            if spousalBenefits[j] > 0:
                aux_on[j] = i

    # Within each year the workers' excess is charged before any auxiliary's own excess
    # (RS 02501.095); excess never carries into another year, so years are independent.
    order = [i for i in range(N_i) if i not in aux_on] + [i for i in range(N_i) if i in aux_on]

    def _charge(own_rate, sp_rate):
        """Charge every year's excess against these monthly rates: (paid_own, paid_sp,
        withheld_own, withheld_sp)."""
        paid_own = own_rate.copy()
        paid_sp = sp_rate.copy()
        withheld_own = np.zeros((N_i, M))
        withheld_sp = np.zeros((N_i, M))
        for n in range(N_n):
            for i in order:
                if excess_by_year[i, n] <= 0:
                    continue
                idx = [m - g0 for m in _year_months(i, n)]
                if not idx:
                    continue
                excess = float(excess_by_year[i, n])
                if i in aux_on:
                    # Auxiliary's own excess: only their remaining check (RS 02501.095 B.3).
                    remaining = [[paid_own[i, k] + paid_sp[i, k] for k in idx]]
                    w_left, _, _ = charge_excess_months(remaining, excess)
                    for pos, k in enumerate(idx):
                        take = w_left[0][pos]
                        tot = paid_own[i, k] + paid_sp[i, k]
                        if take <= 0 or tot <= 0:
                            continue
                        o_share = paid_own[i, k] / tot
                        withheld_own[i, k] += take * o_share
                        withheld_sp[i, k] += take * (1.0 - o_share)
                        paid_own[i, k] -= take * o_share
                        paid_sp[i, k] -= take * (1.0 - o_share)
                else:
                    # Worker's excess: the family on i's record (RS 02501.095 B.2).
                    fam_aux = [k for k, rec in aux_on.items() if rec == i]
                    if fam_aux:
                        j = fam_aux[0]
                        family = [[paid_own[i, k] for k in idx], [paid_sp[j, k] for k in idx]]
                        shares = [float(pias[i]), float(spousalBenefits[j])]
                        if sum(shares) <= 0:
                            shares = None
                    else:
                        family = [[paid_own[i, k] for k in idx]]
                        shares = [float(pias[i])] if pias[i] > 0 else None
                    w_family, _, _ = charge_excess_months(family, excess, shares=shares)
                    for pos, k in enumerate(idx):
                        withheld_own[i, k] += w_family[0][pos]
                        paid_own[i, k] = family[0][pos]
                        if fam_aux:
                            withheld_sp[j, k] += w_family[1][pos]
                            paid_sp[j, k] = family[1][pos]
        return paid_own, paid_sp, withheld_own, withheld_sp

    # Crediting months (RS 00615.482), counted separately on each record (B.3, NOTE):
    # own record, months with a deduction from the own benefit; spouse record, months
    # with a deduction from the spousal add-on, including the worker's charge (B.2).
    # Only months before the person's FRA count: the ARF is computed once, at FRA, from
    # the reduction months; the worker's excess can still reduce a spousal add-on later.
    # They come from a first charge on the pre-ARF rates, which those months carry.
    _, _, withheld_own, withheld_sp = _charge(own, spousal)
    tol = 1e-9
    pre_fra = [max(0, fra_abs[i] - g0) for i in range(N_i)]
    arf_months = np.array(
        [int(np.count_nonzero(withheld_own[i, : pre_fra[i]] > tol)) for i in range(N_i)], dtype=np.int64
    )
    arf_months_sp = np.array(
        [int(np.count_nonzero(withheld_sp[i, : pre_fra[i]] > tol)) for i in range(N_i)], dtype=np.int64
    )

    # --- ARF from FRA (RS 00615.480/.482) --------------------------------------
    # The adjusted benefit is the one entitled from the FRA month (404.412(b)), so a worker's
    # excess charged against a spouse past FRA is charged at it (403(b)(1)): charge again on
    # the adjusted rates rather than scale what the first charge left (#232). Charging runs
    # forward within each year and the rates before FRA are unchanged, so the months before
    # FRA, and with them the crediting months, are charged as in the first pass.
    own_arf = own.copy()
    sp_arf = spousal.copy()
    for i in range(N_i):
        k0 = max(0, fra_abs[i] - g0)
        if arf_months[i] > 0:
            old = getSelfFactor(float(fras[i]), float(ages[i]), born_on_first[i])
            new = arf_self_factor(float(fras[i]), float(ages[i]), int(arf_months[i]), born_on_first[i])
            if old > 0:
                own_arf[i, k0:] *= new / old
        if arf_months_sp[i] > 0:
            old = getSpousalFactor(float(fras[i]), spousal_age[i], born_on_first[i])
            new = arf_spousal_factor(float(fras[i]), spousal_age[i], int(arf_months_sp[i]), born_on_first[i])
            if old > 0:
                sp_arf[i, k0:] *= new / old
    paid_own, paid_sp, withheld_own, withheld_sp = _charge(own_arf, sp_arf)

    # --- Aggregate to annual payment-year amounts (check for month a arrives in a+1)
    zeta_in = np.zeros((N_i, N_n))
    withheld_in = np.zeros((N_i, N_n))
    pay_year_n = (np.arange(M) + g0 + 1) // 12 - thisyear
    for i in range(N_i):
        # Owl's annual stream stops at 12 full months of the last plan year
        # (horizons[i] is the exclusive end); a check paid in that year or later is dropped.
        # The spousal add-on likewise stops with the checks paid in the year before the
        # first death (compute_social_security_benefits: spousal_in[i, ns2:death_year_n]).
        keep = pay_year_n < min(N_n, int(horizons[i]))
        keep_sp = pay_year_n < min(N_n, int(horizons[i]), death_year_n)
        for paid, wh, k in ((paid_own[i], withheld_own[i], keep), (paid_sp[i], withheld_sp[i], keep_sp)):
            np.add.at(zeta_in[i], pay_year_n[k], paid[k])
            np.add.at(withheld_in[i], pay_year_n[k], wh[k])

    # Trim before the survivor fold-in: the survivor stream carries its own trim
    # (same order as compute_social_security_benefits).
    if trim_pct > 0 and trim_year is not None:
        trim_n = max(0, trim_year - thisyear)
        if trim_n < N_n:
            zeta_in[:, trim_n:] *= 1.0 - trim_pct / 100.0
            withheld_in[:, trim_n:] *= 1.0 - trim_pct / 100.0

    if survivor_idx >= 0 and death_year_n < N_n:
        # The deceased's benefit at death includes their ARF if they reached FRA alive
        # (alive through December of the year before death_year_n).
        deceased_factor = None
        d = deceased_idx
        if arf_months[d] > 0 and fra_abs[d] < (thisyear + death_year_n) * 12:
            deceased_factor = arf_self_factor(float(fras[d]), float(ages[d]), int(arf_months[d]), born_on_first[d])
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
            deceased_factor=deceased_factor,
        )
        s = survivor_idx
        zeta_in[s, death_year_n:] = np.maximum(zeta_in[s, death_year_n:], survivor.annual[death_year_n:])

    return EarningsTestResult(
        zeta_in=zeta_in,
        withheld_in=withheld_in,
        arf_months=arf_months,
        ages=ages,
        excess_by_year=excess_by_year,
        arf_months_spousal=arf_months_sp,
    )
