"""
Tax calculation module for 2026 tax year rules.

This module handles all tax calculations including income tax brackets,
capital gains tax, and other tax-related computations based on 2026 tax rules.

Medicare Part B and Part D premiums (including IRMAA surcharges) are modeled.
Part B and Part D use the same MAGI brackets and two-year lookback. Part D
base premium is configurable (default 0); Part D IRMAA amounts follow CMS 2026.

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

from owlplanner.data.irs_590b import JOINT_LIFE_TABLE, UNIFORM_LIFETIME_DIVISOR_BY_AGE

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
        [12_600, 51_270, 124_160, 258_920, 562_960, 565_260, 9_999_999],   # Single
        [25_200, 102_540, 206_840, 315_260, 562_960, 635_920, 9_999_999],  # MFJ
    ]
)

# Permanently superseded by OBBBA; retained for hypothetical yOBBBA modeling only.
stdDeduction_preTCJA = np.array([8_580, 17_160])   # Single, MFJ
#########################################################################

# These are current for 2026 (2025TY).
stdDeduction_OBBBA = np.array([16_100, 32_200])    # Single, MFJ

# These are current for 2026 per individual. Source: IRS Rev. Proc. 2025-32.
extra65Deduction = np.array([2_050, 1_650])        # Single, MFJ (per spouse)

# LTCG bracket thresholds: taxable income above which 15% and 20% rates apply.
# Source: IRS Topic 409, Publication 550. Values indexed for inflation annually.
# Single [0]: 0%→15% at [0], 15%→20% at [1]. MFJ [1]: same structure.
# TODO: Update annually. Verify against IRS.gov/taxtopics/tc409 for current tax year.
capGainRates = np.array(
    [
        [49_450, 545_500],   # Single
        [98_900, 613_700],   # Married filing jointly
    ]
)

###############################################################################
# End of section where rates need to be actualized every year.
###############################################################################

###############################################################################
# ACA Premium Tax Credit constants (updated annually by HHS and IRS).
###############################################################################

# Federal Poverty Level base amounts (48 contiguous states + DC).
# Indexed by household size: [single (1 person), couple (2 persons)].
# Per-year: 2025 HHS, 2026 HHS. For 2027+ we use 2026 until next update.
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
_ACA_CONTRIB_CAP_2025 = 0.085   # ARP/IRA cap above 400% FPL

# 2026 plan year: IRS Rev. Proc. 2025-25. IRA expires; no subsidy above 400%.
# NOTE: As of 2026, Congress has considered extending IRA subsidies (8.5% cap above 400%).
# If an extension is enacted, update to IRA-style rules (0% below 150%, 8.5% cap).
_ACA_BREAKPOINTS_2026 = np.array([1.33, 1.50, 2.00, 2.50, 3.00, 4.00])
_ACA_CONTRIB_PCT_2026 = np.array([0.021, 0.0419, 0.066, 0.0844, 0.0996, 0.0996])
# No cap above 400%: full SLCSP (no PTC)

# ACA LP bracket configuration (2026+ rules; used only in withACA="optimize" mode).
N_ACA_R = 7  # number of ACA brackets: 6 intervals up to 400% FPL + 1 bracket above 400%
# LP bracket thresholds as multiples of FPL (6 thresholds → 7 brackets, constant structure).
_ACA_LP_BREAKPOINTS = _ACA_BREAKPOINTS_2026  # [1.33, 1.50, 2.00, 2.50, 3.00, 4.00]
# Contribution rates per LP bracket (constant-within-bracket approximation of piecewise function).
# Brackets 0-5: 2026 rates. Bracket 6 (>400% FPL): cost = full SLCSP (handled via za*slcsp in plan.py).
_ACA_LP_CONTRIB = np.append(_ACA_CONTRIB_PCT_2026, 0.0)  # r=6 not used in proportional sum

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


def mediVals(yobs, horizons, gamma_n, Nn, Nq, *, include_part_d=True, part_d_base_annual_per_person=0.0):
    """
    Return tuple (nm, L, C) of year index when Medicare starts and vectors L, and C
    defining end points of constant piecewise linear functions representing IRMAA fees.
    Costs C include Part B plus Part D (base + IRMAA) when include_part_d is True.
    Costs C include the fact that one or two individuals have to pay. Eligibility is built-in.

    Part B and Part D use the same MAGI brackets (two-year lookback). Part D base
    is added per eligible person; Part D IRMAA uses CMS 2026 amounts.
    """
    thisyear = date.today().year
    assert Nq == len(partB_irmaa_costs), f"Inconsistent value of Nq: {Nq}."
    assert Nq == len(irmaaBrackets[0]), "Inconsistent IRMAA brackets array."
    Ni = len(yobs)
    # Combined per-person cumulative costs: Part B + Part D IRMAA when enabled
    costs_per_person = partB_irmaa_costs + (partD_irmaa_costs if include_part_d else 0.0)
    # What index year will Medicare start? 65 - age for each individual.
    nm = yobs + 65 - thisyear
    nm = np.maximum(0, nm)
    nmstart = np.min(nm)
    # Has it already started?
    Nmed = Nn - nmstart

    Lbar = np.zeros((Nmed, Nq-1))
    Cbar = np.zeros((Nmed, Nq))

    # Year starts at offset nmstart in the plan. L and C arrays are shorter.
    for nn in range(Nmed):
        imed = 0
        n = nmstart + nn
        if thisyear + n - yobs[0] >= 65 and n < horizons[0]:
            imed += 1
        if Ni == 2 and thisyear + n - yobs[1] >= 65 and n < horizons[1]:
            imed += 1
        if imed:
            if Ni == 1 or not (n < horizons[0] and n < horizons[1]):
                status = 0   # single or one spouse deceased
            else:
                status = 1   # married filing jointly
            Lbar[nn] = gamma_n[n] * irmaaBrackets[status][1:]
            Cbar[nn] = imed * gamma_n[n] * costs_per_person
            if include_part_d and part_d_base_annual_per_person != 0:
                Cbar[nn] += imed * gamma_n[n] * part_d_base_annual_per_person
        else:
            # Nobody is on Medicare this year (e.g. a drawn longevity horizon lands
            # before age 65, or there is a gap between one spouse dying before 65
            # and the other reaching Medicare).  Use single-filer brackets with
            # zero cost so the LP constraints remain valid but impose no charge.
            Lbar[nn] = gamma_n[n] * irmaaBrackets[0][1:]
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


def mediCosts(yobs, horizons, magi, prevmagi, gamma_n, Nn, *, include_part_d=True, part_d_base_annual_per_person=0.0):
    """
    Compute Medicare costs directly (Part B + Part D when include_part_d is True).

    Uses the same MAGI brackets and two-year lookback for both Part B and Part D.
    Part D IRMAA amounts follow CMS 2026. Part D base is optional (configurable).
    """
    thisyear = date.today().year
    Ni = len(yobs)
    fees_b = partB_irmaa_fees
    fees_d = partD_irmaa_fees if include_part_d else np.zeros_like(partB_irmaa_fees)
    costs = np.zeros(Nn)
    for n in range(Nn):
        status = 0 if Ni == 1 else 1 if n < horizons[0] and n < horizons[1] else 0
        for i in range(Ni):
            if thisyear + n - yobs[i] >= 65 and n < horizons[i]:
                # Part B basic premium
                costs[n] += gamma_n[n] * fees_b[0]
                if include_part_d and part_d_base_annual_per_person != 0:
                    costs[n] += gamma_n[n] * part_d_base_annual_per_person
                if n < 2:
                    mymagi = prevmagi[n]
                else:
                    mymagi = magi[n - 2]
                for q in range(1, 6):
                    if mymagi > gamma_n[n] * irmaaBrackets[status][q]:
                        costs[n] += gamma_n[n] * (fees_b[q] + fees_d[q])

    return costs


def _aca_contrib_pct(ratio, breakpoints, contrib_pct):
    """Interpolate contribution percentage from FPL ratio. Caller handles ratio below/above range."""
    idx = int(np.searchsorted(breakpoints, ratio, side='right')) - 1
    idx = max(0, min(idx, len(breakpoints) - 2))
    lo, hi = breakpoints[idx], breakpoints[idx + 1]
    t = (ratio - lo) / (hi - lo)
    return contrib_pct[idx] + t * (contrib_pct[idx + 1] - contrib_pct[idx])


def acaCosts(yobs, horizons, magi_n, gamma_n, slcsp_annual, N_n, thisyear=None, n_aca_start=0):
    """
    Compute net ACA marketplace premium costs (after Premium Tax Credit) for each year.

    The Premium Tax Credit (PTC) = max(0, SLCSP - cap_pct * MAGI), where cap_pct
    is a piecewise-linear function of MAGI/FPL. Net cost = min(SLCSP, cap_pct * MAGI).
    Rules are year-aware: 2025 uses Rev. Proc. 2024-35 (8.5% cap above 400%);
    2026+ uses Rev. Proc. 2025-25 (no subsidy above 400%).

    Eligibility: individual i is ACA-eligible in year n when:
      - thisyear + n - yobs[i] < 65 (not yet on Medicare), AND
      - n < horizons[i] (within planning horizon).

    For a couple where both are pre-65, household size = 2 (joint marketplace plan).
    When only one is pre-65, household size = 1 (individual plan for the remaining person).

    Note: ACA uses current-year MAGI (no 2-year lag like Medicare IRMAA).

    Below 138% FPL the individual qualifies for Medicaid rather than marketplace
    subsidies. This function returns the full SLCSP in that edge case and emits
    no warning; callers should check for Medicaid eligibility if desired.

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
        Plan-year index at which ACA coverage begins. Years before this index are
        skipped (zero cost). Default 0 = coverage from plan start.

    Returns
    -------
    aca_costs_n : array
        Net annual ACA premium (SLCSP minus PTC) after subsidy, per year (plan dollars).
        Zero for years where no individuals are ACA-eligible or slcsp_annual == 0.
    """
    if slcsp_annual <= 0:
        return np.zeros(N_n)

    if thisyear is None:
        thisyear = date.today().year
    Ni = len(yobs)
    costs = np.zeros(N_n)
    fpl_max_year = max(_ACA_FPL.keys())  # Use for calendar years beyond latest

    for n in range(max(0, n_aca_start), N_n):
        # Determine ACA-eligible individuals for this year.
        eligible = [i for i in range(Ni) if thisyear + n - yobs[i] < 65 and n < horizons[i]]
        nelig = len(eligible)
        if nelig == 0:
            continue

        calendar_year = thisyear + n
        fpl_year = calendar_year if calendar_year in _ACA_FPL else fpl_max_year
        fpl_base = _ACA_FPL[fpl_year]

        hh_size = min(nelig, 2)
        fpl = fpl_base[hh_size - 1] * gamma_n[n]
        slcsp = slcsp_annual * gamma_n[n]
        magi = magi_n[n]

        # Below 138% FPL: Medicaid territory; return full premium (no PTC).
        if magi < 1.38 * fpl:
            costs[n] = slcsp
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
            # 2026+ rules: Rev. Proc. 2025-25, no PTC above 400%
            if ratio >= _ACA_BREAKPOINTS_2026[-1]:
                costs[n] = slcsp
                continue
            if ratio < _ACA_BREAKPOINTS_2026[0]:
                cap_pct = _ACA_CONTRIB_PCT_2026[0]
            else:
                cap_pct = _aca_contrib_pct(ratio, _ACA_BREAKPOINTS_2026, _ACA_CONTRIB_PCT_2026)

        costs[n] = min(slcsp, cap_pct * magi)

    return costs


def acaVals(yobs, horizons, gamma_n, slcsp_annual, Nn, n_aca_start=0):
    """
    Return (n_aca, Lbar_aca_nr, cap_pct_aca_r, slcsp_aca_n) for the ACA LP/MIP formulation.

    Uses 2026+ ACA rules (N_ACA_R = 7 brackets). Bracket thresholds are FPL-based and
    inflation-adjusted via gamma_n. Household size (1 or 2) determines which FPL base to use.
    FPL base is year-aware (2025 vs 2026 from _ACA_FPL); contribution rates use 2026 table only.

    Limitations:
      - No year-awareness for contribution rates: always 2026 rules. Plans starting in 2025
        use 2026 rates; SC-loop mode (acaCosts) is year-aware.
      - MAGI below 138% FPL: LP uses bracket 0 at 2.1% instead of full SLCSP (Medicaid).

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

    Returns
    -------
    n_aca : int
        Number of ACA-eligible plan years (0 = no ACA in LP).
    Lbar_aca_nr : ndarray, shape (n_aca, N_ACA_R-1)
        Inflation-adjusted FPL bracket thresholds per year ($).
    cap_pct_aca_r : ndarray, shape (N_ACA_R,)
        Contribution rates per bracket (constant across years).
    slcsp_aca_n : ndarray, shape (n_aca,)
        Inflation-adjusted SLCSP premium cap per year ($). Zero for nn < n_aca_start.
    """
    empty = (0, np.zeros((0, N_ACA_R - 1)), _ACA_LP_CONTRIB.copy(), np.zeros(0))
    if slcsp_annual <= 0:
        return empty

    thisyear = date.today().year
    Ni = len(yobs)
    fpl_max_year = max(_ACA_FPL.keys())

    # n_aca = first year when no individual is ACA-eligible (age < 65 and within horizon).
    n_aca_i = [min(max(0, yobs[i] + 65 - thisyear), horizons[i]) for i in range(Ni)]
    n_aca = min(max(n_aca_i), Nn)

    if n_aca == 0:
        return empty

    Lbar = np.zeros((n_aca, N_ACA_R - 1))
    slcsp_aca_n = np.zeros(n_aca)

    for nn in range(n_aca):
        if nn < n_aca_start:
            continue  # Before ACA coverage starts; arrays stay zero (LP pins maca=0 via zero slcsp cap)
        n = nn  # ACA uses current year (no 2-year lag like Medicare)
        eligible = [i for i in range(Ni) if thisyear + n - yobs[i] < 65 and n < horizons[i]]
        hh_size = min(len(eligible), 2)
        if hh_size == 0:
            continue  # No ACA-eligible individuals this year; thresholds stay zero

        calendar_year = thisyear + n
        fpl_year = calendar_year if calendar_year in _ACA_FPL else fpl_max_year
        fpl = _ACA_FPL[fpl_year][hh_size - 1] * gamma_n[n]

        Lbar[nn] = _ACA_LP_BREAKPOINTS * fpl
        slcsp_aca_n[nn] = slcsp_annual * gamma_n[n]

    return n_aca, Lbar, _ACA_LP_CONTRIB.copy(), slcsp_aca_n


def taxParams(yobs, i_d, n_d, N_n, gamma_n, MAGI_n, yOBBBA=_YEAR_FAR_FUTURE):
    """
    Input is year of birth, index of shortest-lived individual,
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
                    sigmaBar[n] += max(0, 6000 - 0.06*max(0, MAGI_n[n] - bonusThreshold[filingStatus]))

        # Fill in future tax rates for year n.
        if thisyear + n < yOBBBA:
            theta[n, :] = rates_OBBBA[:]
        else:
            theta[n, :] = rates_preTCJA[:]

    Delta = Delta.transpose()
    theta = theta.transpose()

    # Return series unadjusted for inflation, except for sigmaBar, in STD order.
    return sigmaBar, theta, Delta


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
        raise RuntimeError(
            "RMD: Unsupported life expectancy over 120 years."
        )

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
