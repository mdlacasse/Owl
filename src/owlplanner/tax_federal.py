"""
Tax calculation module for 2026 tax year rules.

This module handles all tax calculations including income tax brackets,
capital gains tax, and other tax-related computations based on 2026 tax rules.

Medicare Part B and Part D premiums (including IRMAA surcharges) are modeled.
Part B and Part D use the same MAGI brackets and two-year lookback. Part D
base premium is configurable (default 0); Part D IRMAA amounts follow CMS 2026.

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
"""

import numpy as np
from datetime import date

from owlplanner.data.irs_590b import JOINT_LIFE_TABLE, UNIFORM_LIFETIME_DIVISOR_BY_AGE
from owlplanner.data.aca_age_rating import couple_to_individual_fraction

# Sentinel: used as default yOBBBA meaning "OBBBA never expires / far future".
_YEAR_FAR_FUTURE = 2099

###############################################################################
# Start of section where rates need to be actualized every year.
###############################################################################
# Single [0] and married filing jointly [1].

# OBBBA §1002 — 65+ additional "bonus" deduction expires after this tax year.
OBBBA_BONUS_EXPIRATION_YEAR = 2028

# These are current for 2026 (2025TY).
taxBrackets_OBBBA = np.array(
    [
        [12_400, 50_400, 105_700, 201_775, 256_225, 640_600, 9_999_999],
        [24_800, 100_800, 211_400, 403_550, 512_450, 768_700, 9_999_999],
    ]
)

# These are current for 2026 (2025TY).
irmaaBrackets = np.array(
    [
        [0, 109_000, 137_000, 171_000, 205_000, 500_000],
        [0, 218_000, 274_000, 342_000, 410_000, 750_000],
    ]
)

# BBA 2018 froze the top IRMAA tier at $500k/$750k in nominal dollars; CPI indexing starts in 2028.
IRMAA_TOP_TIER_INDEXED_FROM = 2028

# These are current for 2026 (2025TY). Source: CMS 2026 Part B premiums and IRMAA.
# Index [0] stores the standard Medicare Part B basic premium (monthly $202.90 for 2026).
# Following values are incremental IRMAA Part B monthly fees; cumulative = total/month.
# Single brackets [0]: ≤$109k, $109–137k, $137–171k, $171–205k, $205–500k, ≥$500k.
partB_irmaa_fees = 12 * np.array([202.90, 81.20, 121.70, 121.70, 121.70, 40.70])
partB_irmaa_costs = np.cumsum(partB_irmaa_fees)

# Part D IRMAA: same 6 brackets as Part B. Source: CMS 2026 Part D IRMAA.
# Monthly surcharges per bracket (cumulative): $0, $14.50, $36.30, $58.10, $79.90, $91.00.
# Stored as incremental monthly fees (bracket 0 = 0; brackets 1–5 = surcharge increments).
partD_irmaa_monthly = np.array([0.0, 14.50, 21.80, 21.80, 21.80, 11.10])
partD_irmaa_fees = 12 * partD_irmaa_monthly
partD_irmaa_costs = np.cumsum(partD_irmaa_fees)

#########################################################################
# Make projection for pre-TCJA using 2017 to current year.
# taxBrackets_2017 = np.array(
#    [ [9_325, 37_950, 91_900, 191_650, 416_700, 418_400, 9_999_999],
#      [18_650, 75_900, 153_100, 233_350, 416_700, 470_700, 9_999_999],
#    ])
#
# stdDeduction_2017 = [6350, 12700]
#
# COLA from 2017: [2.0, 2.8, 1.6, 1.3, 5.9, 8.7, 3.2, 2.5, 2.8]
# For 2026, I used a 35.1% adjustment from 2017, rounded to closest 10.
#
# These are permanently superseded by OBBBA (signed 2025) and retained only for
# hypothetical modeling scenarios (yOBBBA parameter). They will not apply unless
# a future Congress reinstates pre-TCJA law.
taxBrackets_preTCJA = np.array(
    [
        [12_600, 51_270, 124_160, 258_920, 562_960, 565_260, 9_999_999],  # Single
        [25_200, 102_540, 206_840, 315_260, 562_960, 635_920, 9_999_999],  # MFJ
    ]
)

# Permanently superseded by OBBBA; retained for hypothetical yOBBBA modeling only.
stdDeduction_preTCJA = np.array([8_580, 17_160])  # Single, MFJ
#########################################################################

# These are current for 2026 (2025TY).
stdDeduction_OBBBA = np.array([16_100, 32_200])  # Single, MFJ

# These are current for 2026 per individual. Source: IRS Rev. Proc. 2025-32.
extra65Deduction = np.array([2_050, 1_650])  # Single, MFJ (per spouse)

# LTCG bracket thresholds: taxable income above which 15% and 20% rates apply.
# Source: IRS Topic 409, Publication 550. Values indexed for inflation annually.
# Single [0]: 0%→15% at [0], 15%→20% at [1]. MFJ [1]: same structure.
# TODO: Update annually. Verify against IRS.gov/taxtopics/tc409 for current tax year.
capGainRates = np.array(
    [
        [49_450, 545_500],  # Single
        [98_900, 613_700],  # Married filing jointly
    ]
)

# Retirement-account contribution limits (IRS-published, indexed for inflation).
# Source: IRS Notice 2025-67 (tax year 2026); IRS Notice 2024-80 (tax year 2025).
# TODO: Update annually — the IRS typically announces next year's limits in
# late October / early November of the prior year.

# Elective deferral limit for 401(k), 403(b), governmental 457(b), and TSP plans.
electiveDeferralLimit = {2025: 23_500, 2026: 24_500}

# Age 50+ catch-up contribution for the plans above.
electiveDeferralCatchup50 = {2025: 7_500, 2026: 8_000}

# SECURE 2.0 Act "super" catch-up for individuals who turn 60-63 during the tax
# year (available starting 2025). Replaces -- does not stack with -- the 50+
# catch-up above for those four ages.
electiveDeferralCatchup60to63 = {2025: 11_250, 2026: 11_250}

# Traditional/Roth IRA combined annual contribution limit (per person).
iraContributionLimit = {2025: 7_000, 2026: 7_500}

# IRA catch-up contribution for individuals age 50+ by year-end.
iraCatchup50 = {2025: 1_000, 2026: 1_100}

# HSA annual contribution limits: [self-only coverage, family coverage].
hsaContributionLimit = {
    2025: np.array([4_300, 8_550]),
    2026: np.array([4_400, 8_750]),
}

# HSA catch-up for individuals age 55+ by year-end. Fixed by statute (not
# inflation-indexed) since HSAs were introduced in 2003.
HSA_CATCHUP_55 = 1_000

# Annual per-person exclusion limit for Qualified Charitable Distributions
# (IRC 408(d)(8)), inflation-indexed since SECURE 2.0.
qcdLimit = {2025: 108_000, 2026: 115_000}

# IRS sets the limit above one year at a time, but plans run decades, so beyond the
# table it is carried forward at this fixed rate: the geometric mean of CPI over
# Owl's full rate history, 1928-2025 (data/rates.csv). Deliberately a constant and
# not the scenario's own inflation -- this figure only ever validates user input,
# and a scenario-dependent bound would accept an entry on one Monte Carlo path and
# reject it on the next.
QCD_LIMIT_INFLATION = 0.030

# A QCD may be made on or after the day the owner reaches age 70 1/2 -- which is
# not the RMD start age (see rho_in), and did not move with SECURE 1.0/2.0.
QCD_MIN_AGE = 70.5

###############################################################################
# End of section where rates need to be actualized every year.
###############################################################################

###############################################################################
# ACA Premium Tax Credit constants (updated annually by HHS and IRS).
###############################################################################

# HHS poverty guidelines (48 contiguous states + DC), keyed by the year they were published.
# Indexed by household size: [single (1 person), couple (2 persons)].
# Coverage in year Y uses the guideline of year Y-1: see _aca_fpl.
_ACA_FPL = {
    2025: np.array([15_650.0, 21_150.0]),
    2026: np.array([15_960.0, 21_640.0]),
}
# Default for backward compatibility and lookup
acaFPL = _ACA_FPL[2025]

# 2025 plan year: IRS Rev. Proc. 2024-35. IRA suspends indexing; 8.5% cap above 400%.
# Breakpoints: 150%, 200%, 250%, 300%, 400%. Below 150%: 0%.
_ACA_BREAKPOINTS_2025 = np.array([1.50, 2.00, 2.50, 3.00, 4.00])
_ACA_CONTRIB_PCT_2025 = np.array([0.0, 0.02, 0.04, 0.06, 0.085])
_ACA_CONTRIB_CAP_2025 = 0.085  # ARP/IRA cap above 400% FPL

# 2026 plan year: IRS Rev. Proc. 2025-25. IRA expires; no subsidy above 400%.
# NOTE: As of 2026, Congress has considered extending IRA subsidies (8.5% cap above 400%).
# If an extension is enacted, update to IRA-style rules (0% below 150%, 8.5% cap).
_ACA_BREAKPOINTS_2026 = np.array([1.33, 1.50, 2.00, 2.50, 3.00, 4.00])
_ACA_CONTRIB_PCT_2026 = np.array([0.021, 0.0419, 0.066, 0.0844, 0.0996, 0.0996])
# Initial percentage of each band that starts at a breakpoint (133-150%, ..., 300-400%). The table
# jumps at 133%: below it 2.10%, from it 3.14% rising to 4.19% at 150%. The other bands start where
# the previous one ends.
_ACA_CONTRIB_INITIAL_2026 = np.array([0.0314, 0.0419, 0.066, 0.0844, 0.0996])
# No cap above 400%: full SLCSP (no PTC)

# 2027 taxable year: IRS Rev. Proc. 2026-26, sec. 3.01. Same breakpoints as 2026.
_ACA_CONTRIB_PCT_2027 = np.array([0.0215, 0.043, 0.0678, 0.0866, 0.1022, 0.1022])
_ACA_CONTRIB_INITIAL_2027 = np.array([0.0323, 0.043, 0.0678, 0.0866, 0.1022])

# Applicable percentage tables of the 2026+ rules, keyed by taxable year: (breakpoints, percentage
# at the top of each band with the below-133% rate first, initial percentage of each band).
# A year past the last table uses the last one: see _aca_table.
_ACA_TABLES = {
    2026: (_ACA_BREAKPOINTS_2026, _ACA_CONTRIB_PCT_2026, _ACA_CONTRIB_INITIAL_2026),
    2027: (_ACA_BREAKPOINTS_2026, _ACA_CONTRIB_PCT_2027, _ACA_CONTRIB_INITIAL_2027),
}

# Below 138% FPL the household is assumed covered by Medicaid, at no premium. That is the rule in
# expansion states; in the others there is no Medicaid for most adults and the marketplace rules
# apply from 100% FPL, which is not modeled.
_ACA_MEDICAID_RATIO = 1.38

# ACA LP bracket configuration (2026+ rules; used only in withACA="optimize" mode).
N_ACA_R = 7  # number of ACA brackets: 6 intervals up to 400% FPL + 1 bracket above 400%
# LP bracket thresholds as multiples of FPL (6 thresholds → 7 brackets, constant structure).
# Bracket 0 (below 138%): Medicaid, no premium. Brackets 1-5: the 2026 sliding scale, priced by
# tangent lines (see acaVals). Bracket 6 (400% and up): full SLCSP (za * slcsp in plan.py).
_ACA_LP_BREAKPOINTS = np.array([_ACA_MEDICAID_RATIO, 1.50, 2.00, 2.50, 3.00, 4.00])
# Tangent lines per bracket under the sliding-scale cost pct(MAGI) * MAGI, which is convex within a
# bracket. Their maximum follows the cost from below, exactly at the tangent points; with four
# evenly spaced points the shortfall is a few dollars at most.
_ACA_LP_TANGENTS = 4

###############################################################################
# Data that is unlikely to change.
###############################################################################

# Thresholds for net investment income tax (not adjusted for inflation).
niitThreshold = np.array([200_000, 250_000])
niitRate = 0.038

# Thresholds for 65+ bonus of $6k per individual for circumventing tax
# on social security for low-income households. This expires in 2029.
# These numbers are hard-coded below as the tax code will likely change
# the rules for eligibility and will require a code review.
# Bonus decreases by $6 per $100 of MAGI above threshold; fully phased out
# at threshold + $100,000 (i.e., $175k single / $250k MFJ).
bonusThreshold = np.array([75_000, 150_000])
SENIOR_BONUS = 6000.0  # per individual aged 65 or older, not indexed
SENIOR_BONUS_PHASEOUT_RATE = 0.06  # $6 per $100 of MAGI above the threshold

# IRS Social Security taxability thresholds (frozen since 1983/1994 — not inflation-indexed).
# Provisional income formula: PI = MAGI - 0.5*SS. Below lo: 0% taxable; lo-hi: 50% ramp;
# above hi: up to 85% taxable. [Single, MFJ].
ssTaxabilityLo = np.array([25_000.0, 32_000.0])
ssTaxabilityHi = np.array([34_000.0, 44_000.0])

taxBracketNames = ["10%", "12/15%", "22/25%", "24/28%", "32/33%", "35%", "37/40%"]

rates_OBBBA = np.array([0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.370])
rates_preTCJA = np.array([0.10, 0.15, 0.25, 0.28, 0.33, 0.35, 0.396])

###############################################################################


def compute_social_security_taxability(N_i, MAGI_n, ss_n, ssec_tax_fraction=None, n_d=None):
    """
    Compute the fraction of Social Security benefits subject to federal income tax
    using the IRS provisional income (PI) formula.

    PI = MAGI - 0.5 * SS (MAGI already includes full SS).
    IRS thresholds (frozen in nominal dollars since 1983/1994):
      - Married filing jointly: 0% below $32k, ramp to 50% at $44k, 85% above $44k
      - Single:                 0% below $25k, ramp to 50% at $34k, 85% above $34k

    For a couple, filing status switches from MFJ to Single in the year n_d when
    the first spouse dies; n_d is the index of that year (pass n_d when N_i == 2).

    From table in IRS publication 915:

    Taxable_n = min(0.85*ss_n,
                    0.50*min(ss_n, hi - lo, max(0, PI - lo)) + 0.85*max(0, PI - hi))

    Parameters
    ----------
    N_i : int
        Number of individuals (1 or 2)
    MAGI_n : array
        Modified adjusted gross income per year
    ss_n : array
        Total Social Security benefits per year
    ssec_tax_fraction : float or None
        If provided, return constant array with this value (overrides PI computation)
    n_d : int or None
        Index year when first spouse dies (N_i==2 only). If None, MFJ is used for all years.

    Returns
    -------
    Psi_n : array
        Fraction of SS taxable per year, in [0, 0.85]
    """
    N_n = len(MAGI_n)
    if ssec_tax_fraction is not None:
        return np.full(N_n, ssec_tax_fraction)

    # Filing status per year: for couples, switch from MFJ (1) to Single (0) at n_d.
    status_n = np.full(N_n, N_i - 1)
    if N_i == 2 and n_d is not None and n_d < N_n:
        status_n[n_d:] = 0

    lo_n = ssTaxabilityLo[status_n]
    hi_n = ssTaxabilityHi[status_n]

    pi_n = MAGI_n - 0.5 * ss_n

    # 50% tier: 0.50 * min(ss_n, hi - lo, max(0, PI - lo)); in [lo, hi), PI - lo < hi - lo.
    amount_50 = 0.5 * np.minimum(ss_n, np.minimum(hi_n - lo_n, np.maximum(0.0, pi_n - lo_n)))
    # 85% tier: 0.85 * max(0, PI - hi); total capped at 0.85*ss_n.
    amount_85_extra = 0.85 * np.maximum(0.0, pi_n - hi_n)
    taxable_ss = np.where(
        pi_n < lo_n,
        0.0,
        np.where(
            pi_n < hi_n,
            amount_50,
            np.minimum(amount_50 + amount_85_extra, 0.85 * ss_n),
        ),
    )
    new_Psi_n = np.full(N_n, 0.85)
    mask = ss_n > 0
    new_Psi_n[mask] = np.minimum(taxable_ss[mask] / ss_n[mask], 0.85)
    return new_Psi_n


def irmaaThresholds(status, gamma_n, n, thisyear):
    """
    Return the nominal IRMAA thresholds (tiers 1-5) for plan year n.

    Lower tiers follow gamma_n. The top tier stays at its nominal value through the
    bill year before IRMAA_TOP_TIER_INDEXED_FROM and follows inflation from then on.
    """
    scale = np.full(len(irmaaBrackets[status]) - 1, gamma_n[n])
    nfrozen = IRMAA_TOP_TIER_INDEXED_FROM - 1 - thisyear
    if nfrozen >= 0:
        scale[-1] = gamma_n[n] / gamma_n[nfrozen] if n > nfrozen else 1.0
    return scale * irmaaBrackets[status][1:]


def medicareMonths(yobs, horizons, N_n, mobs=None, tobs=None, thisyear=None, ages=None):
    """
    Months of Medicare coverage for each individual in each plan year, shape (N_i, N_n).

    Coverage starts in the month of the 65th birthday, or in the month before when the birthday
    falls on the 1st: "For an individual whose 65th birthday is on the first day of the month,
    Part A coverage begins on the first day of the month preceding their birth month" (CMS,
    Original Medicare (Part A and B) Eligibility and Enrollment). A January 1 birthday therefore
    starts coverage in December of the year before. Premiums are monthly, and a month with Medicare
    is not an ACA coverage month (IRC 36B(c)(2)(B), 5000A(f)(1)(A)(i)), so this count drives both
    the first Medicare year and the last ACA year (issues #199, #208).

    Without birth months (mobs, tobs None), coverage starts in January of the year of the 65th
    birthday: the yearly model. Years from horizons[i] on, the individual is gone and has 0 months.
    ages, when given, replaces 65 with each individual's enrollment age, for someone who delays
    Medicare; coverage then starts in the month of that birthday.
    """
    if thisyear is None:
        thisyear = date.today().year
    yobs = np.asarray(yobs, dtype=int)
    Ni = len(yobs)
    mobs = np.ones(Ni, dtype=int) if mobs is None else np.asarray(mobs, dtype=int)
    tobs = np.full(Ni, 2, dtype=int) if tobs is None else np.asarray(tobs, dtype=int)
    ages = np.full(Ni, 65, dtype=int) if ages is None else np.asarray(ages, dtype=int)
    months = np.zeros((Ni, N_n), dtype=int)
    for i in range(Ni):
        start_year, start_month = yobs[i] + ages[i], mobs[i]
        if tobs[i] == 1:
            start_month -= 1
            if start_month == 0:
                start_year, start_month = start_year - 1, 12
        for n in range(min(N_n, max(0, horizons[i]))):
            year = thisyear + n
            if year > start_year:
                months[i, n] = 12
            elif year == start_year:
                months[i, n] = 13 - start_month
    return months


def medicareStartYear(yobs, mobs=None, tobs=None):
    """Calendar year of each individual's first Medicare month (see medicareMonths)."""
    yobs = np.asarray(yobs, dtype=int)
    if mobs is None or tobs is None:
        return yobs + 65
    return yobs + 65 - ((np.asarray(mobs) == 1) & (np.asarray(tobs) == 1)).astype(int)


def mediVals(yobs, horizons, gamma_n, Nn, Nq, *, include_part_d=True, part_d_base_annual_per_person=0.0,
             medical_n=None, mobs=None, tobs=None):
    """
    Return tuple (nm, L, C) of year index when Medicare starts and vectors L, and C
    defining end points of constant piecewise linear functions representing IRMAA fees.
    Costs C include Part B plus Part D (base + IRMAA) when include_part_d is True.
    Costs C include the fact that one or two individuals have to pay. Eligibility is built-in.

    Part B and Part D use the same MAGI brackets (two-year lookback). Part D base
    is added per eligible person; Part D IRMAA uses CMS 2026 amounts.

    Bracket thresholds follow gamma_n (they are indexed to CPI), except the top tier,
    which is frozen in nominal dollars before 2028 (see irmaaThresholds). Premiums follow medical_n,
    which defaults to gamma_n; pass a faster series when medical prices outgrow inflation.
    Each individual pays for the months of coverage in the year (medicareMonths, from birth months
    mobs and days tobs), so the first year is prorated.
    """
    if medical_n is None:
        medical_n = gamma_n
    thisyear = date.today().year
    assert Nq == len(partB_irmaa_costs), f"Inconsistent value of Nq: {Nq}."
    assert Nq == len(irmaaBrackets[0]), "Inconsistent IRMAA brackets array."
    Ni = len(yobs)
    # Combined per-person cumulative costs: Part B + Part D IRMAA when enabled
    costs_per_person = partB_irmaa_costs + (partD_irmaa_costs if include_part_d else 0.0)
    # What index year will Medicare start? The year of the first month of coverage.
    nm = medicareStartYear(yobs, mobs, tobs) - thisyear
    nm = np.maximum(0, nm)
    months_in = medicareMonths(yobs, horizons, Nn, mobs, tobs, thisyear)
    # A plan can end before anyone reaches 65: then Medicare never starts within it.
    nmstart = min(int(np.min(nm)), Nn)
    # Has it already started?
    Nmed = Nn - nmstart

    Lbar = np.zeros((Nmed, Nq - 1))
    Cbar = np.zeros((Nmed, Nq))

    # Year starts at offset nmstart in the plan. L and C arrays are shorter.
    for nn in range(Nmed):
        n = nmstart + nn
        # Individuals paying premiums this year, each for the fraction of the year covered.
        imed = np.sum(months_in[:, n]) / 12
        if imed:
            if Ni == 1 or not (n < horizons[0] and n < horizons[1]):
                status = 0  # single or one spouse deceased
            else:
                status = 1  # married filing jointly
            Lbar[nn] = irmaaThresholds(status, gamma_n, n, thisyear)
            Cbar[nn] = imed * medical_n[n] * costs_per_person
            if include_part_d and part_d_base_annual_per_person != 0:
                Cbar[nn] += imed * medical_n[n] * part_d_base_annual_per_person
        else:
            # Nobody is on Medicare this year (e.g. a drawn longevity horizon lands
            # before age 65, or there is a gap between one spouse dying before 65
            # and the other reaching Medicare).  Use single-filer brackets with
            # zero cost so the LP constraints remain valid but impose no charge.
            Lbar[nn] = irmaaThresholds(0, gamma_n, n, thisyear)
            # Cbar[nn] stays at zero (already initialized)

    return nmstart, Lbar, Cbar


def capitalGainTax(Ni, txIncome_n, ltcg_n, gamma_n, nd, Nn):
    """
    Return an array of tax on capital gains.

    Parameters:
    -----------
    Ni : int
        Number of individuals (1 or 2)
    txIncome_n : array
        Array of taxable income for each year (ordinary income + capital gains)
    ltcg_n : array
        Array of long-term capital gains for each year
    gamma_n : array
        Array of inflation adjustment factors for each year
    nd : int
        Index year of first passing of a spouse, if applicable (nd == Nn for single individuals)
    Nn : int
        Total number of years in the plan

    Returns:
    --------
    cgTax_n : array
        Array of tax on capital gains for each year

    Notes:
    ------
    Thresholds are determined by the taxable income which is roughly AGI - (standard/itemized) deductions.
    Taxable income can also be thought of as taxable ordinary income + capital gains.

    Long-term capital gains are taxed at 0%, 15%, or 20% based on total taxable income.
    Capital gains "stack on top" of ordinary income, so the portion of gains that
    pushes total income above each threshold is taxed at the corresponding rate.
    """
    status = Ni - 1
    cgTax_n = np.zeros(Nn)

    for n in range(Nn):
        if status and n == nd:
            status -= 1

        # Calculate ordinary income (taxable income minus capital gains).
        ordIncome = txIncome_n[n] - ltcg_n[n]

        # Get inflation-adjusted thresholds for this year.
        threshold15 = gamma_n[n] * capGainRates[status][0]  # 0% to 15% threshold
        threshold20 = gamma_n[n] * capGainRates[status][1]  # 15% to 20% threshold

        # Calculate how much LTCG falls in the 20% bracket.
        # This is the portion of LTCG that pushes total income above threshold20.
        if txIncome_n[n] > threshold20:
            ltcg20 = min(ltcg_n[n], txIncome_n[n] - threshold20)
        else:
            ltcg20 = 0

        # Calculate how much LTCG falls in the 15% bracket.
        # This is the portion of LTCG in the range [threshold15, threshold20].
        if ordIncome >= threshold20:
            # All LTCG is already in the 20% bracket.
            ltcg15 = 0
        elif txIncome_n[n] > threshold15:
            # Some LTCG falls in the 15% bracket.
            # The 15% bracket spans from threshold15 to threshold20.
            bracket_top = min(threshold20, txIncome_n[n])
            bracket_bottom = max(threshold15, ordIncome)
            ltcg15 = min(ltcg_n[n] - ltcg20, bracket_top - bracket_bottom)
        else:
            # Total income is below the 15% threshold.
            ltcg15 = 0

        # Remaining LTCG is in the 0% bracket (ltcg0 = ltcg_n[n] - ltcg20 - ltcg15).
        # Calculate tax: 20% on ltcg20, 15% on ltcg15, 0% on remainder.
        cgTax_n[n] = 0.20 * ltcg20 + 0.15 * ltcg15

    return cgTax_n


def mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, *, include_part_d=True, part_d_base_annual_per_person=0.0,
              medical_n=None, mobs=None, tobs=None):
    """
    Compute Medicare costs directly (Part B + Part D when include_part_d is True).

    Uses the same MAGI brackets and two-year lookback for both Part B and Part D.
    Part D IRMAA amounts follow CMS 2026. Part D base is optional (configurable).
    Thresholds follow irmaaThresholds and premiums follow medical_n (default gamma_n), as in mediVals.
    Each individual pays for the months of coverage in the year (medicareMonths), as in mediVals.
    """
    if medical_n is None:
        medical_n = gamma_n
    thisyear = date.today().year
    Ni = len(yobs)
    fees_b = partB_irmaa_fees
    fees_d = partD_irmaa_fees if include_part_d else np.zeros_like(partB_irmaa_fees)
    costs = np.zeros(Nn)
    months_in = medicareMonths(yobs, horizons, Nn, mobs, tobs, thisyear)
    for n in range(Nn):
        status = 0 if Ni == 1 else 1 if n < horizons[0] and n < horizons[1] else 0
        thresholds = irmaaThresholds(status, gamma_n, n, thisyear)
        for i in range(Ni):
            if months_in[i, n]:
                frac = months_in[i, n] / 12
                # Part B basic premium
                costs[n] += frac * medical_n[n] * fees_b[0]
                if include_part_d and part_d_base_annual_per_person != 0:
                    costs[n] += frac * medical_n[n] * part_d_base_annual_per_person
                if n < 2:
                    mymagi = prevmagi[n]
                else:
                    mymagi = magi[n - 2]
                for q in range(1, 6):
                    if mymagi > thresholds[q - 1]:
                        costs[n] += frac * medical_n[n] * (fees_b[q] + fees_d[q])

    return costs


def _aca_table(calendar_year):
    """Applicable percentage table (breakpoints, pct, initial pct) for coverage in calendar_year.

    The table is published for each taxable year (IRC 36B(b)(3)(A)); a year past the last one
    published uses the last one, and a year before the first uses the first.
    """
    years = [y for y in _ACA_TABLES if y <= calendar_year]
    return _ACA_TABLES[max(years) if years else min(_ACA_TABLES)]


def _aca_fpl(calendar_year, size, gamma_n, thisyear):
    """
    Poverty line ($) for ACA coverage in calendar_year, for a tax household of size 1 or 2.

    The line is "the most recently published poverty line as of the 1st day of the regular
    enrollment period" (IRC 36B(d)(3)(B); 26 CFR 1.36B-1(h)). Open enrollment for year Y starts in
    November of Y-1, so coverage in Y uses the guideline published in Y-1 (#200). A published
    guideline is used as is. A year past the last one published grows it by inflation from its own
    year, gamma_n from plan year latest - thisyear to z - thisyear, and a year before the first
    deflates the first likewise. Before the plan, inflation is taken at the plan's first-year rate.
    """
    z = calendar_year - 1
    if z in _ACA_FPL:
        return float(_ACA_FPL[z][size - 1])

    rate = gamma_n[1] / gamma_n[0] if len(gamma_n) > 1 else 1.0

    def growth(k):
        if k < 0:
            return gamma_n[0] * rate**k
        if k >= len(gamma_n):
            return gamma_n[-1] * rate ** (k - len(gamma_n) + 1)
        return gamma_n[k]

    base = max(_ACA_FPL) if z > max(_ACA_FPL) else min(_ACA_FPL)
    return float(_ACA_FPL[base][size - 1] * growth(z - thisyear) / growth(base - thisyear))


def _aca_contrib_pct(ratio, breakpoints, contrib_pct, initial_pct=None):
    """Interpolate contribution percentage from FPL ratio. Caller handles ratio below/above range.

    The band from breakpoints[k] to breakpoints[k+1] runs from initial_pct[k] to contrib_pct[k+1].
    Without initial_pct each band starts where the previous one ends (initial_pct[k] = contrib_pct[k]).
    """
    idx = int(np.searchsorted(breakpoints, ratio, side="right")) - 1
    idx = max(0, min(idx, len(breakpoints) - 2))
    lo, hi = breakpoints[idx], breakpoints[idx + 1]
    t = (ratio - lo) / (hi - lo)
    start = contrib_pct[idx] if initial_pct is None else initial_pct[idx]
    return start + t * (contrib_pct[idx + 1] - start)


def _aca_coverage(yobs, horizons, N_n, mobs, tobs, thisyear):
    """
    The ACA household and coverage families of each plan year, by the month.

    Returns (family_n, parts_n). family_n[n] is the family size for the poverty line: the tax
    household, 2 while both spouses are alive and 1 after the first death, whoever is enrolled
    (IRC 36B(d)(1); 26 CFR 1.36B-1(d)(2): "including both spouses in the case of a joint return",
    issue #199). parts_n[n] lists (months, scale): the months of the year with one coverage family,
    the members enrolled that month (26 CFR 1.36B-3(b)(2)), and the share of the household
    benchmark that covers them, since the benchmark follows the coverage family month by month
    (1.36B-3(f)(1), Example 7). An individual is enrolled in the months before Medicare
    (medicareMonths), which come first in the year; a lone enrollee of a couple is covered by
    couple_to_individual_fraction of the couple's benchmark.
    """
    Ni = len(yobs)
    med = medicareMonths(yobs, horizons, N_n, mobs, tobs, thisyear)
    family_n = np.zeros(N_n, dtype=int)
    parts_n = []
    for n in range(N_n):
        alive = [i for i in range(Ni) if n < horizons[i]]
        family_n[n] = len(alive)
        aca = {i: 12 - int(med[i, n]) for i in alive if med[i, n] < 12}
        parts = []
        if len(aca) == 2:
            both = min(aca.values())
            parts.append((both, 1.0))
            j = max(aca, key=aca.get)
            if aca[j] > both:
                parts.append((aca[j] - both, couple_to_individual_fraction(thisyear + n - yobs[j])))
        elif len(aca) == 1:
            ((j, months),) = aca.items()
            parts.append((months, couple_to_individual_fraction(thisyear + n - yobs[j]) if Ni == 2 else 1.0))
        parts_n.append(parts)
    return family_n, parts_n


def acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual, N_n, thisyear=None, n_aca_start=0, medical_n=None,
             mobs=None, tobs=None):
    """
    Compute net ACA marketplace premium costs (after Premium Tax Credit) for each year.

    The Premium Tax Credit (PTC) = max(0, SLCSP - cap_pct * MAGI), where cap_pct
    is a piecewise-linear function of MAGI/FPL. Net cost = min(SLCSP, cap_pct * MAGI).
    Rules are year-aware: 2025 uses Rev. Proc. 2024-35 (8.5% cap above 400%); 2026 on has no
    subsidy above 400% and uses the year's applicable percentage table (Rev. Proc. 2025-25 for 2026,
    2026-26 for 2027, the last one after that; see _aca_table). Income of exactly 400% FPL still
    qualifies: IRC 36B(c)(1)(A) covers income that "does not exceed 400 percent" (#201). The poverty
    line is the guideline published the year before (_aca_fpl, #200).

    Coverage is by the month (IRC 36B(b)): an individual is enrolled in the months of year n before
    Medicare starts (medicareMonths, from birth months mobs and days tobs) while within the planning
    horizon. Each coverage month costs the lesser of that month's benchmark and 1/12 of the
    expected contribution. The poverty line is that of the tax household, 2 for a couple while both
    are alive, even when one spouse is on Medicare (#199). When only one partner is enrolled, the
    benchmark is the couple's scaled by the CMS age rating fraction
    (f_younger / (f_older + f_younger)), the remaining partner's individual plan (see _aca_coverage).

    Note: ACA uses current-year MAGI (no 2-year lag like Medicare IRMAA).

    Up to and including 138% FPL the household is assumed covered by Medicaid, at no premium (the
    rule in expansion states; non-expansion states are not modeled).

    Parameters
    ----------
    yobs : array-like
        Year of birth for each individual.
    horizons : array-like
        Planning horizon (year index) for each individual.
    magi_n : array
        Modified Adjusted Gross Income per plan year, length N_n (plan dollars).
    gamma_n : array
        Inflation factors per year, length >= N_n.
    slcsp_annual : float
        Today-dollar annual benchmark Silver plan (SLCSP) premium for the full
        household. Inflated internally using gamma_n.
    N_n : int
        Number of plan years.
    thisyear : int, optional
        Plan start year. Defaults to date.today().year. Used for testing.
    n_aca_start : int, optional
        Plan year index when ACA coverage begins (default 0 = plan start).
        Years before this index are set to zero regardless of eligibility.
    medical_n : array, optional
        Growth factors for the SLCSP premium, length >= N_n. Defaults to gamma_n; pass a
        faster series when medical prices outgrow inflation. The poverty line follows gamma_n.

    Returns
    -------
    aca_costs_n : array
        Net annual ACA premium (SLCSP minus PTC) after subsidy, per year (plan dollars).
        Zero for years where no individuals are ACA-eligible or slcsp_annual == 0.
    """
    if slcsp_annual <= 0:
        return np.zeros(N_n)
    if medical_n is None:
        medical_n = gamma_n

    if thisyear is None:
        thisyear = date.today().year
    costs = np.zeros(N_n)

    family_n, parts_n = _aca_coverage(yobs, horizons, N_n, mobs, tobs, thisyear)

    for n in range(max(0, n_aca_start), N_n):
        if not parts_n[n]:
            continue  # nobody enrolled this year

        calendar_year = thisyear + n
        fpl = _aca_fpl(calendar_year, family_n[n], gamma_n, thisyear)
        slcsp = slcsp_annual * medical_n[n]
        magi = magi_n[n]

        # Up to 138% FPL (133% plus the 5% income disregard): Medicaid, no premium.
        if magi <= _ACA_MEDICAID_RATIO * fpl:
            continue

        ratio = magi / fpl
        if calendar_year < 2026:
            # 2025 rules: Rev. Proc. 2024-35, 8.5% cap above 400%
            if ratio < _ACA_BREAKPOINTS_2025[0]:
                cap_pct = 0.0
            elif ratio >= _ACA_BREAKPOINTS_2025[-1]:
                cap_pct = _ACA_CONTRIB_CAP_2025
            else:
                cap_pct = _aca_contrib_pct(ratio, _ACA_BREAKPOINTS_2025, _ACA_CONTRIB_PCT_2025)
        else:
            # 2026+ rules: the year's table, no PTC above 400% (exactly 400% still qualifies)
            breakpoints, pct, initial = _aca_table(calendar_year)
            if ratio > breakpoints[-1]:
                cap_pct = np.inf
            elif ratio < breakpoints[0]:
                cap_pct = pct[0]
            else:
                cap_pct = _aca_contrib_pct(ratio, breakpoints, pct, initial)

        # Each coverage month pays the lesser of its benchmark and 1/12 of the contribution.
        contribution = cap_pct * magi
        costs[n] = sum(months / 12 * min(scale * slcsp, contribution) for months, scale in parts_n[n])

    return costs


def _aca_lp_band(r, table=None):
    """(lower, upper, pct at lower, pct at upper) of LP bracket r (1..5), as multiples of FPL.

    table is the year's applicable percentage table (_aca_table); defaults to the 2026 one.
    """
    breakpoints, pct, initial = _ACA_TABLES[2026] if table is None else table
    lo, hi = _ACA_LP_BREAKPOINTS[r - 1], _ACA_LP_BREAKPOINTS[r]
    p_lo = _aca_contrib_pct(lo, breakpoints, pct, initial)
    p_hi = _aca_contrib_pct(hi - 1e-12, breakpoints, pct, initial)
    return lo, hi, p_lo, p_hi


def _aca_band_cost_coefs(r, fpl, table=None):
    """Coefficients (a, b) of the bracket's cost a*M + b*M**2 in MAGI dollars M.

    The applicable percentage rises linearly across the bracket, p = p_lo + s*(M/fpl - lo), so the
    expected contribution p*M is quadratic in M and convex (b >= 0).
    """
    lo, hi, p_lo, p_hi = _aca_lp_band(r, table)
    s = (p_hi - p_lo) / (hi - lo)
    return p_lo - s * lo, s / fpl


def _aca_tangents(fpl, table=None):
    """Tangent lines (slope, intercept) under each bracket's cost, shape (N_ACA_R, K, 2), in dollars.

    Bracket 0 (Medicaid) and bracket 6 (full SLCSP) have no proportional cost and stay zero.
    """
    tan = np.zeros((N_ACA_R, _ACA_LP_TANGENTS, 2))
    for r in range(1, N_ACA_R - 1):
        lo, hi, _, _ = _aca_lp_band(r, table)
        a, b = _aca_band_cost_coefs(r, fpl, table)
        for k, x in enumerate(np.linspace(lo, hi, _ACA_LP_TANGENTS)):
            m = x * fpl
            tan[r, k] = (a + 2 * b * m, -b * m * m)
    return tan


def _aca_capped_limits(fpl, slcsp, table=None):
    """LP bracket thresholds ($), clipped at the MAGI where the expected contribution reaches the SLCSP.

    The net premium is min(SLCSP, contribution). The contribution only rises with MAGI, so from the
    first MAGI where it reaches the SLCSP every higher income pays the full premium: the cost of the
    last bracket. Clipping the thresholds there moves those incomes into the last bracket, and the
    brackets above the crossing get zero width (issue #161). The crossing is found on the sliding
    scale, where the cost is quadratic in MAGI within a bracket.
    """
    limits = _ACA_LP_BREAKPOINTS * fpl
    if slcsp <= 0:
        return np.zeros_like(limits)  # no premium: every income in the last bracket, at no cost
    for r in range(1, N_ACA_R - 1):
        lo, hi, _, p_hi = _aca_lp_band(r, table)
        if slcsp > p_hi * hi * fpl:
            continue  # the whole bracket costs less than the SLCSP
        a, b = _aca_band_cost_coefs(r, fpl, table)
        if b > 0:
            m_star = (-a + np.sqrt(a * a + 4 * b * slcsp)) / (2 * b)
        else:
            m_star = slcsp / a
        return np.minimum(limits, max(lo * fpl, m_star))
    return limits


def acaVals(yobs, horizons, gamma_n, slcsp_annual, Nn, n_aca_start=0, medical_n=None, mobs=None, tobs=None):
    """
    Return (n_aca, Lbar_aca_nr, tangents_aca_nrk, slcsp_aca_n) for the ACA LP/MIP formulation.

    Uses 2026+ ACA rules (N_ACA_R = 7 brackets). Bracket thresholds are multiples of the poverty
    line of the tax household (1 or 2), the guideline published the year before (_aca_fpl, #200).
    Each year uses its applicable percentage table (_aca_table, #201). Income of exactly 400% FPL
    stays in bracket 5, whose upper bound is inclusive. Coverage months and benchmarks follow
    _aca_coverage, as in acaCosts.

    Limitations:
      - A plan starting in 2025 is priced on the 2026 rules; SC-loop mode (acaCosts) applies the
        2025 rules to that year.
      - Below 138% FPL: bracket 0, Medicaid at no premium, as in acaCosts.
      - Within brackets 1-5 the cost follows the sliding scale through tangent lines, slightly from
        below between tangent points.
      - A year with two coverage families (one partner moving to Medicare during the year) is
        priced on their months-weighted benchmark: min(sum of benchmarks, months/12 * contribution)
        rather than acaCosts's sum of the families' lesser amounts. That keeps one premium cap per
        year and charges slightly more, only for MAGI between the two caps.

    Parameters
    ----------
    yobs : array-like
        Year of birth for each individual.
    horizons : array-like
        Planning horizon (year index) for each individual.
    gamma_n : array
        Inflation factors per year, length >= Nn.
    slcsp_annual : float
        Today-dollar annual benchmark Silver plan premium for the full household.
    Nn : int
        Number of plan years.
    n_aca_start : int, optional
        Plan-year index at which ACA coverage begins. Years before this index are zeroed
        (e.g. still on employer coverage). Default 0 = coverage from plan start.
    medical_n : array, optional
        Growth factors for the SLCSP premium, length >= Nn. Defaults to gamma_n.

    Returns
    -------
    n_aca : int
        Number of ACA-eligible plan years (0 = no ACA in LP).
    Lbar_aca_nr : ndarray, shape (n_aca, N_ACA_R-1)
        Inflation-adjusted FPL bracket thresholds per year ($), clipped at the MAGI where the
        contribution reaches the SLCSP (see _aca_capped_limits).
    tangents_aca_nrk : ndarray, shape (n_aca, N_ACA_R, _ACA_LP_TANGENTS, 2)
        Per year and bracket, the (slope, intercept) of tangent lines under the bracket's cost in
        dollars of MAGI; the cost charged is the largest of them.
    slcsp_aca_n : ndarray, shape (n_aca,)
        Inflation-adjusted SLCSP premium cap per year ($). Zero for nn < n_aca_start.
    """
    empty = (0, np.zeros((0, N_ACA_R - 1)), np.zeros((0, N_ACA_R, _ACA_LP_TANGENTS, 2)), np.zeros(0))
    if slcsp_annual <= 0:
        return empty
    if medical_n is None:
        medical_n = gamma_n

    thisyear = date.today().year

    # n_aca = the year after the last one with anybody enrolled.
    family_n, parts_n = _aca_coverage(yobs, horizons, Nn, mobs, tobs, thisyear)
    covered = [n for n in range(Nn) if parts_n[n]]
    n_aca = covered[-1] + 1 if covered else 0

    if n_aca == 0:
        return empty

    Lbar = np.zeros((n_aca, N_ACA_R - 1))
    tangents = np.zeros((n_aca, N_ACA_R, _ACA_LP_TANGENTS, 2))
    slcsp_aca_n = np.zeros(n_aca)

    for nn in range(n_aca):
        if nn < n_aca_start:
            continue  # Before ACA coverage starts; arrays stay zero (LP pins maca=0 via zero slcsp cap)
        n = nn  # ACA uses current year (no 2-year lag like Medicare)
        if not parts_n[n]:
            continue  # Nobody enrolled this year; thresholds stay zero

        calendar_year = thisyear + n
        fpl = _aca_fpl(calendar_year, family_n[n], gamma_n, thisyear)
        table = _aca_table(calendar_year)

        # The year's benchmark is the sum over its coverage months, and the contribution is owed
        # for the fraction of the year with anybody enrolled.
        frac = sum(months for months, _ in parts_n[n]) / 12
        slcsp_aca_n[nn] = slcsp_annual * medical_n[n] * sum(months * scale for months, scale in parts_n[n]) / 12
        Lbar[nn] = _aca_capped_limits(fpl, slcsp_aca_n[nn] / frac, table)
        tangents[nn] = frac * _aca_tangents(fpl, table)

    return n_aca, Lbar, tangents, slcsp_aca_n


def taxBirthYears(yobs, mobs, tobs):
    """
    Birth years as the federal age-65 tests count them, for taxParams and seniorBonusSchedule.

    The additional standard deduction (IRC 63(f)) and the OBBBA senior deduction
    (IRC 151(d)(5)(C)(ii), Pub. L. 119-21 sec. 70103) require having attained age 65 before the
    close of the taxable year, and the IRS treats a person as reaching an age on the day before the
    birthday: "A person is considered to reach age 65 on the day before the person's 65th birthday"
    (2025 Instructions for Form 1040). A January 1 birthday therefore counts in the year before,
    which is why the 2025 instructions read "born before January 2, 1961".
    """
    yobs = np.asarray(yobs)
    return yobs - ((np.asarray(mobs) == 1) & (np.asarray(tobs) == 1)).astype(yobs.dtype)


def taxParams(yobs, i_d, n_d, N_n, gamma_n, MAGI_n, yOBBBA=_YEAR_FAR_FUTURE):
    """
    Input is year of birth (as returned by taxBirthYears), index of shortest-lived individual,
    lifespan of shortest-lived individual, total number of years
    in the plan, and the year that preTCJA rates might come back.

    It returns 3 time series:
    1) Standard deductions at year n (sigma_n).
    2) Tax rate in year n (theta_tn)
    3) Delta from top to bottom of tax brackets (Delta_tn)
    This is pure speculation on future values.
    Returned values are not indexed for inflation.
    """
    # Compute the deltas in-place between brackets, starting from the end.
    deltaBrackets_OBBBA = np.array(taxBrackets_OBBBA)
    deltaBrackets_preTCJA = np.array(taxBrackets_preTCJA)
    for t in range(6, 0, -1):
        for i in range(2):
            deltaBrackets_OBBBA[i, t] -= deltaBrackets_OBBBA[i, t - 1]
            deltaBrackets_preTCJA[i, t] -= deltaBrackets_preTCJA[i, t - 1]

    # Prepare the 3 arrays to return - use transpose for easy slicing.
    sigmaBar = np.zeros((N_n))
    Delta = np.zeros((N_n, 7))
    theta = np.zeros((N_n, 7))

    filingStatus = len(yobs) - 1
    souls = list(range(len(yobs)))
    thisyear = date.today().year

    for n in range(N_n):
        # First check if shortest-lived individual is still with us.
        if n == n_d:
            souls.remove(i_d)
            filingStatus -= 1

        if thisyear + n < yOBBBA:
            sigmaBar[n] = stdDeduction_OBBBA[filingStatus] * gamma_n[n]
            Delta[n, :] = deltaBrackets_OBBBA[filingStatus, :]
        else:
            sigmaBar[n] = stdDeduction_preTCJA[filingStatus] * gamma_n[n]
            Delta[n, :] = deltaBrackets_preTCJA[filingStatus, :]

        # Add 65+ additional exemption(s) and "bonus" phasing out.
        for i in souls:
            if thisyear + n - yobs[i] >= 65:
                sigmaBar[n] += extra65Deduction[filingStatus] * gamma_n[n]
                if thisyear + n <= OBBBA_BONUS_EXPIRATION_YEAR:
                    excess = max(0, MAGI_n[n] - bonusThreshold[filingStatus])
                    sigmaBar[n] += max(0, SENIOR_BONUS - SENIOR_BONUS_PHASEOUT_RATE * excess)

        # Fill in future tax rates for year n.
        if thisyear + n < yOBBBA:
            theta[n, :] = rates_OBBBA[:]
        else:
            theta[n, :] = rates_preTCJA[:]

    Delta = Delta.transpose()
    theta = theta.transpose()

    # Return series unadjusted for inflation, except for sigmaBar, in STD order.
    return sigmaBar, theta, Delta


def seniorBonusSchedule(yobs, i_d, n_d, N_n):
    """
    The OBBBA 65+ bonus deduction by plan year, as taxParams applies it.

    Returns (count_n, threshold_n): the number of individuals who receive the bonus in year n
    (0 outside the bonus years, or when nobody is 65 or older), and the MAGI threshold of that
    year's filing status, above which each individual's bonus shrinks by
    SENIOR_BONUS_PHASEOUT_RATE per dollar, down to zero.
    Birth years yobs are as returned by taxBirthYears.
    """
    count_n = np.zeros(N_n, dtype=int)
    threshold_n = np.zeros(N_n)
    filingStatus = len(yobs) - 1
    souls = list(range(len(yobs)))
    thisyear = date.today().year
    for n in range(N_n):
        if n == n_d:
            souls.remove(i_d)
            filingStatus -= 1
        threshold_n[n] = bonusThreshold[filingStatus]
        if thisyear + n <= OBBBA_BONUS_EXPIRATION_YEAR:
            count_n[n] = sum(1 for i in souls if thisyear + n - yobs[i] >= 65)
    return count_n, threshold_n


def taxBrackets(N_i, n_d, N_n, yOBBBA=_YEAR_FAR_FUTURE):
    """
    Return dictionary containing future tax brackets
    unadjusted for inflation for plotting.
    """
    if not (0 < N_i <= 2):
        raise ValueError(f"Cannot process {N_i} individuals.")

    n_d = min(n_d, N_n)
    status = N_i - 1

    # Number of years left in OBBBA from this year.
    thisyear = date.today().year
    if yOBBBA < thisyear:
        raise ValueError(f"OBBBA expiration year {yOBBBA} cannot be in the past.")

    ytc = yOBBBA - thisyear

    data = {}
    for t in range(len(taxBracketNames) - 1):
        array = np.zeros(N_n)
        for n in range(N_n):
            stat = status if n < n_d else 0
            array[n] = taxBrackets_OBBBA[stat][t] if n < ytc else taxBrackets_preTCJA[stat][t]

        data[taxBracketNames[t]] = array

    return data


def computeNIIT(N_i, MAGI_n, I_n, Q_n, n_d, N_n):
    """
    Compute ACA tax on dividends (Q), interest (I), and other net investment income.
    I_n already includes rent and trust income from the 'net inv' column of the HFP.
    """
    J_n = np.zeros(N_n)
    status = N_i - 1

    for n in range(N_n):
        if status and n == n_d:
            status -= 1

        Gmax = niitThreshold[status]
        if MAGI_n[n] > Gmax:
            J_n[n] = niitRate * min(MAGI_n[n] - Gmax, I_n[n] + Q_n[n])

    return J_n


def rho_in(yobs, longevity, N_n):
    """
    Return Required Minimum Distribution fractions for each individual.

    RMD ages by birth year (SECURE 1.0 / SECURE 2.0 Act):
      - Born before 1949:   RMD age 70  (pre-SECURE 1.0)
      - Born 1949–1950:     RMD age 72  (SECURE 1.0, effective 2020)
      - Born 1951–1959:     RMD age 73  (SECURE 2.0 Act §107, effective 2023)
      - Born 1960 or later: RMD age 75  (SECURE 2.0 Act §107, effective 2033)

    Uses IRS Publication 590-B (effective 2022) tables:
      - Table III (Uniform Lifetime): single filers and married couples with
        spouse 10 or fewer years younger, or when spouse is no longer alive.
      - Table II (Joint and Last Survivor): married couples where the spouse is
        the sole designated beneficiary, more than 10 years younger than the
        account owner, and still alive. Table starts at age 72; index [0] = age 72 (divisor 27.4).

    Limitations:
      - Inherited IRA / beneficiary RMD rules are not modeled.
      - RMDs apply only to tax-deferred accounts (j=1). Roth accounts (j=2) are
        exempt; Roth 401(k) RMDs were eliminated by SECURE 2.0 §325 for 2024+.
      - The spouse is assumed to be the sole designated beneficiary (not verified).
      - Age difference is computed from birth years; at the 10-year boundary, this
        may differ by 1 year from actual Dec 31 ages depending on birth months.
    """
    N_i = len(yobs)
    if np.any(np.array(longevity) > 120):
        raise RuntimeError("RMD: Unsupported life expectancy over 120 years.")

    rho = np.zeros((N_i, N_n))
    thisyear = date.today().year
    for i in range(N_i):
        agenow = thisyear - yobs[i]
        # Account for increase of RMD age between 2023 and 2032.
        yrmd = 70 if yobs[i] < 1949 else 72 if 1949 <= yobs[i] <= 1950 else 73 if 1951 <= yobs[i] <= 1959 else 75
        # Use Table II when spouse is sole beneficiary and >10 years younger.
        j = 1 - i  # index of the other spouse
        use_table2 = N_i == 2 and (yobs[j] - yobs[i]) > 10
        # Spouse's planning horizon (years from thisyear); after this, revert to Table III.
        spouse_horizon = yobs[j] + longevity[j] - thisyear + 1 if use_table2 else N_n
        for n in range(N_n):
            yage = agenow + n

            if yage < yrmd:
                pass  # rho[i][n] = 0
            elif use_table2 and n < spouse_horizon:
                # IRS Pub 590-B Table II (Joint and Last Survivor)
                spouse_age = (thisyear - yobs[j]) + n
                owner_key = min(max(yage, 20), 120)
                spouse_key = min(max(spouse_age, 20), 120)
                rho[i][n] = 1.0 / JOINT_LIFE_TABLE[owner_key][spouse_key]
            else:
                rho[i][n] = 1.0 / UNIFORM_LIFETIME_DIVISOR_BY_AGE[yage]

    return rho


def _limit_for_year(table, year):
    """Return table[year], clamped to the nearest tabulated year if out of range."""
    years = sorted(table)
    if year <= years[0]:
        return table[years[0]]
    if year >= years[-1]:
        return table[years[-1]]
    return table[year]


def qcdLimitForYear(year):
    """
    Per-person QCD exclusion limit for a calendar year.

    Published figures are exact; later years carry the last published figure
    forward at QCD_LIMIT_INFLATION. Earlier years clamp to the first figure.
    """
    last = max(qcdLimit)
    if year <= last:
        return float(_limit_for_year(qcdLimit, year))
    return float(qcdLimit[last] * (1.0 + QCD_LIMIT_INFLATION) ** (year - last))


def contributionLimits(birth_year, tax_year=None):
    """
    Return IRS contribution-limit ceilings for a person born in birth_year,
    for tax_year (default: the current calendar year).

    Catch-up eligibility follows IRS convention: based on the age the person
    attains by December 31 of tax_year (birth_year alone is sufficient --
    birth month/day do not affect eligibility).

    Returns a dict with "base", "catchup", and "max" (= base + catchup) for:
      - "elective_deferral": 401(k)/403(b)/governmental 457(b)/TSP employee
        contributions. Ages 60-63 get the SECURE 2.0 "super" catch-up instead
        of the standard 50+ catch-up.
      - "ira": Traditional + Roth IRA combined annual limit (per person).
      - "hsa_self_only" / "hsa_family": HSA contribution limit by coverage tier;
        the 55+ catch-up is the same for either tier.

    This reports statutory ceilings only -- it does NOT check income-based
    eligibility (e.g. Roth IRA MAGI phase-outs, traditional IRA deductibility
    phase-outs when covered by an employer plan, or HSA-eligible high-deductible
    health plan enrollment).
    """
    if tax_year is None:
        tax_year = date.today().year

    age_eoy = tax_year - birth_year

    ed_base = int(_limit_for_year(electiveDeferralLimit, tax_year))
    if 60 <= age_eoy <= 63:
        ed_catchup = int(_limit_for_year(electiveDeferralCatchup60to63, tax_year))
    elif age_eoy >= 50:
        ed_catchup = int(_limit_for_year(electiveDeferralCatchup50, tax_year))
    else:
        ed_catchup = 0

    ira_base = int(_limit_for_year(iraContributionLimit, tax_year))
    ira_catchup = int(_limit_for_year(iraCatchup50, tax_year)) if age_eoy >= 50 else 0

    hsa_self, hsa_family = (int(v) for v in _limit_for_year(hsaContributionLimit, tax_year))
    hsa_catchup = HSA_CATCHUP_55 if age_eoy >= 55 else 0

    return {
        "tax_year": tax_year,
        "age_in_tax_year": age_eoy,
        "elective_deferral": {"base": ed_base, "catchup": ed_catchup, "max": ed_base + ed_catchup},
        "ira": {"base": ira_base, "catchup": ira_catchup, "max": ira_base + ira_catchup},
        "hsa_self_only": {"base": hsa_self, "catchup": hsa_catchup, "max": hsa_self + hsa_catchup},
        "hsa_family": {"base": hsa_family, "catchup": hsa_catchup, "max": hsa_family + hsa_catchup},
    }
