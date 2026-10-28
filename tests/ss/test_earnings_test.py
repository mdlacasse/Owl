"""
Tests for the SSA earnings-test rules (``socialsecurity.earnings_test`` and its helpers).

Expected values come from the primary worked examples, not from the code under test.
Each test names its source. Exempt amounts are passed in so the POMS examples run
with their own year's numbers.

Sources (POMS on secure.ssa.gov, read 2026-10-18):
  RS 02501.025 D  exempt amounts (TN 55, 11/21/2025)
  RS 02501.030    monthly test / grace year / non-service months
  RS 02501.080    excess examples (TN 39)
  RS 02501.095    family charging examples (TN 38)
  RS 02501.110    partial-month split examples (TN 47)
  RS 00615.480/.482/.490  ARF procedure (TN 77/76/24)
  20 CFR 404.435 Example 1  grace year (eCFR 2026-10-15 text)

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

import math

import numpy as np
import pytest

from owlplanner import socialsecurity as ss

# Month indexing (locked API — do not mix them):
#   charge_excess_months: 0-based month index within the charged span (0 = first month).
#   is_non_service_month / initial_grace_year: 1-based calendar month (1 = January).


# Frozen plan start (tests/conftest.py freezes the date; keep this in step with it).
THISYEAR = 2026

# 2026 statutory amounts (RS 02501.025 D, TN 55).
_EXEMPT_2026_VALUES = (24_480.0, 65_160.0)


def _exempt_2026(_year):
    return ss.ExemptAmounts(*_EXEMPT_2026_VALUES)


# --------------------------------------------------------------------------------------
# Excess earnings — RS 02501.080
# --------------------------------------------------------------------------------------


def test_excess_under_fra_rounds_down():
    """RS 02501.080 B.1 EXAMPLE: $12,121 − $9,600 → $1,260 (1999 amounts)."""
    # ($12,121 − $9,600) / 2 = $1,260.5 → $1,260 rounded down.
    assert ss.excess_earnings(12_121.0, 9_600.0, is_fra_year=False) == 1260


def test_excess_fra_year_divides_by_three():
    """RS 02501.080 B.2 EXAMPLE: $30,000 − $17,000 → $4,333 (FRA-year amounts)."""
    # ($30,000 − $17,000) / 3 = $4,333.33 → $4,333 rounded down.
    assert ss.excess_earnings(30_000.0, 17_000.0, is_fra_year=True) == 4333


def test_excess_fra_year_wage_cut_at_fra_month():
    """RS 02501.080 B.2.b EXAMPLE: attained FRA in 6/00; Jan-May $30,000, Jun-Dec $10,000.

    Only $30,000 counts; excess = ($30,000 − $17,000) / 3 = $4,333.

    Owl spreads earnings evenly over ``months worked``, which matches the
    NESE prorating of B.2.c, not the wages month-by-month shape of B.2.b (the example's
    $30k/$10k split cannot be expressed as an even spread). What must hold: only the
    months *before* the FRA month count, and the FRA-year divisor is 3.
    """
    # Example as written (uneven wages): the rule applied to the pre-FRA total.
    assert ss.excess_earnings(30_000.0, 17_000.0, is_fra_year=True) == 4333
    # Even-spread form of the cut: 5 of 12 months before June.
    countable = ss.countable_earnings(40_000.0, months_worked=12, is_fra_year=True, fra_month_in_year=6)
    assert countable == pytest.approx(40_000.0 * 5 / 12)
    # A worker whose months-worked period is entirely before the FRA month counts all of it.
    assert ss.countable_earnings(30_000.0, months_worked=5, is_fra_year=True, fra_month_in_year=6) == 30_000.0
    # FRA in January: no month before the FRA month counts.
    assert ss.countable_earnings(10_000.0, months_worked=12, is_fra_year=True, fra_month_in_year=1) == 0.0
    # FRA month past the last worked month: the whole year counts.
    assert ss.countable_earnings(40_000.0, 12, is_fra_year=True, fra_month_in_year=13) == pytest.approx(
        40_000.0
    )


def test_excess_never_negative():
    assert ss.excess_earnings(10_000.0, 24_480.0, is_fra_year=False) == 0
    assert ss.excess_earnings(24_480.0, 24_480.0, is_fra_year=False) == 0


# --------------------------------------------------------------------------------------
# Family charging — RS 02501.095
# --------------------------------------------------------------------------------------


def test_nh_excess_charges_family_three_months():
    """RS 02501.095 B.2 EXAMPLE: NH RIB $378, spouse and child $160 each, excess $2,094.

    Family $698/month; January-March withheld (3 × $698 = $2,094).
    """
    monthly = [[378.0] * 12, [160.0] * 12, [160.0] * 12]
    withheld, n_ded, partial = ss.charge_excess_months(monthly, 2094.0)
    assert n_ded == 3
    assert partial is None
    for m in range(3):
        assert withheld[0][m] == pytest.approx(378.0)
        assert withheld[1][m] == pytest.approx(160.0)
        assert withheld[2][m] == pytest.approx(160.0)
    for m in range(3, 12):
        assert withheld[0][m] == 0
        assert withheld[1][m] == 0
        assert withheld[2][m] == 0


def test_aux_excess_after_nh_four_then_five_months():
    """RS 02501.095 B.4 EXAMPLE: NH RIB $346, spouse $173; NH excess $2,076; spouse $865.

    NH's excess: January-April against family $519 (4 × $519 = $2,076).
    Spouse's own excess then charges May-September against $173 (5 × $173 = $865).

    This unit test drives the two passes explicitly. The *order* (NH first, then aux)
    as ``earnings_test`` behavior is asserted in
    ``test_family_charge_order_and_spousal_arf_crediting``.
    """
    # First: NH worker excess against the family.
    family = [[346.0] * 12, [173.0] * 12]
    w1, n1, _ = ss.charge_excess_months(family, 2076.0)
    assert n1 == 4
    for m in range(4):
        assert w1[0][m] == pytest.approx(346.0)
        assert w1[1][m] == pytest.approx(173.0)
        assert family[0][m] == 0
        assert family[1][m] == 0

    # Then: auxiliary's own excess against what is left of the aux benefit.
    remaining = [[family[1][m] for m in range(12)]]  # spouse's remaining check
    w2, n2, _ = ss.charge_excess_months(remaining, 865.0)
    assert n2 == 5
    for m in range(5):
        # May-September are months 4..8 of the year (0-based).
        assert w2[0][4 + m] == pytest.approx(173.0)
    for m in (0, 1, 2, 3, 9, 10, 11):
        assert w2[0][m] == 0


def test_no_carry_over_into_next_year():
    """RS 02501.095 B.1: excess of one year is never charged into the next.

    A year with a small benefit and a large excess exhausts that year's months
    and leaves the rest of the excess uncharged (it does not spill into the next
    year's months).
    """
    # One beneficiary, $100/month, excess $300: 3 months charged, nothing more.
    monthly = [[100.0] * 12]
    withheld, n_ded, _ = ss.charge_excess_months(monthly, 300.0)
    assert n_ded == 3
    assert sum(withheld[0]) == pytest.approx(300.0)
    # Larger excess than the year's family benefit: all 12 months, remainder dropped.
    monthly = [[100.0] * 12]
    withheld, n_ded, _ = ss.charge_excess_months(monthly, 10_000.0)
    assert n_ded == 12
    assert sum(withheld[0]) == pytest.approx(1200.0)


# --------------------------------------------------------------------------------------
# Partial last month — RS 02501.110
# --------------------------------------------------------------------------------------


def test_partial_month_split_in_proportion():
    """RS 02501.110 C EXAMPLE 2: NH $800, four aux at $101, excess $6,624.

    Family $1,204; January-May full; June pays the family $600, split NH $200
    and each auxiliary $100 (2/6 and 1/6 shares).
    """
    monthly = [[800.0] * 12] + [[101.0] * 12 for _ in range(4)]
    shares = [2.0, 1.0, 1.0, 1.0, 1.0]
    withheld, n_ded, partial = ss.charge_excess_months(monthly, 6624.0, shares=shares)
    assert n_ded == 6
    assert partial == 5  # June (0-based)
    for m in range(5):
        assert withheld[0][m] == pytest.approx(800.0)
    # June: family paid $600 → NH $200, each aux $100; withheld = rate − paid.
    assert monthly[0][5] == pytest.approx(200.0)
    for b in range(1, 5):
        assert monthly[b][5] == pytest.approx(100.0)
    assert withheld[0][5] == pytest.approx(600.0)
    for b in range(1, 5):
        assert withheld[b][5] == pytest.approx(1.0)


def test_partial_month_share_capped_at_rate():
    """RS 02501.110 C EXAMPLE 3 (first apportionment + reapportionment).

    Partial family benefit $93; NH $117, aged spouse $16, two children $19.90.
    Shares 2:1:1:1. First split NH $37.20, each other $18.60; the spouse is capped
    at $16 and $2.60 is reapportioned (NH +$1.30, each child +$0.65) →
    NH $38, spouse $16, each child $19 (rounded down).
    """
    rates = [117.0, 16.0, 19.90, 19.90]
    shares = [2.0, 1.0, 1.0, 1.0]
    family = sum(rates)  # 172.80
    # Pay $93 in June: withhold family - 93 = 79.80 from that month.
    monthly = [[rates[b]] * 12 for b in range(4)]
    excess = family - 93.0
    withheld, n_ded, partial = ss.charge_excess_months(monthly, excess, shares=shares, start=5)
    assert partial == 5
    assert n_ded == 1
    # Paid amounts in the partial month (exact share math, then the dollar floor).
    # POMS Exhibit 3 pays the floored dollars: $38 / $16 / $19 / $19.
    assert monthly[0][5] == pytest.approx(38.50)
    assert monthly[1][5] == pytest.approx(16.0)
    assert monthly[2][5] == pytest.approx(19.25)
    assert monthly[3][5] == pytest.approx(19.25)
    assert math.floor(monthly[0][5]) == 38
    assert math.floor(monthly[1][5]) == 16
    assert math.floor(monthly[2][5]) == 19
    assert math.floor(monthly[3][5]) == 19


# --------------------------------------------------------------------------------------
# Non-service months and the grace year — RS 02501.030 / 404.435
# --------------------------------------------------------------------------------------


def test_non_service_month_definitions():
    """404.435(a)(7): no work, or wages at or below the monthly exempt amount."""
    assert ss.is_non_service_month(1, 0.0, 0, 2040.0) is True
    # $24,000/12 = $2,000 <= $2,040 monthly exempt → non-service.
    assert ss.is_non_service_month(1, 24_000.0, 12, 2040.0) is True
    # $30,000/12 = $2,500 > $2,040 → service month.
    assert ss.is_non_service_month(1, 30_000.0, 12, 2040.0) is False
    # After the months-worked period: no wages that month.
    assert ss.is_non_service_month(7, 40_000.0, 6, 2040.0) is True
    assert ss.is_non_service_month(6, 40_000.0, 6, 2040.0) is False


def test_grace_year_claim_in_july_with_six_months_work():
    """Claim in July of the last work year, `months worked` = 6 → nothing withheld.

    July-December are non-service months in or after entitlement, so the year is the
    initial grace year and the monthly test pays those months in full (404.435 Example 1
    is the same shape: retire mid-year, later months paid although annual earnings
    exceed the exempt amount).
    """
    # Hand-built year-level check of the grace-year rule.
    earn = {2028: 40_000.0}
    months = {2028: 6}
    grace = ss.initial_grace_year(
        earn,
        ent_start_month_in_year=7,
        start_year=2028,
        exempt_for_year=_exempt_2026,
        months_worked_by_year=months,
    )
    assert grace == 2028


def test_grace_year_claim_in_july_with_twelve_months_work_is_not_spared():
    """Same with `months worked` = 12 → the annual test applies (no non-service month)."""
    earn = {2028: 40_000.0}
    months = {2028: 12}
    # Every month has wages above the monthly exempt amount ($3,333 > $2,040),
    # so there is no non-service month in 2028.
    for m in range(1, 13):
        assert ss.is_non_service_month(m, 40_000.0, 12, 2040.0) is False
    grace = ss.initial_grace_year(
        earn,
        ent_start_month_in_year=7,
        start_year=2028,
        exempt_for_year=_exempt_2026,
        months_worked_by_year=months,
    )
    assert grace is None


def test_second_year_with_non_service_months_gets_no_grace():
    """Only one initial grace year (404.435(b)); a later year gets the annual test only."""
    earn = {2026: 0.0, 2027: 50_000.0, 2028: 0.0}
    months = {2026: 0, 2027: 12, 2028: 0}
    grace = ss.initial_grace_year(
        earn,
        ent_start_month_in_year=1,
        start_year=2026,
        exempt_for_year=_exempt_2026,
        months_worked_by_year=months,
        end_year=2028,
    )
    # 2026 has no work → non-service months → grace year is 2026, not 2028.
    assert grace == 2026


def test_year_after_entitlement_with_no_earnings_uses_up_grace():
    """404.435(a)(7),(b): claim in 2026 while not working; work above the limit in 2027.

    2026 is the initial grace year (all months non-service). 2027 is then the annual
    test only: no non-service months are spared. Hand pin: claim 62y1m
    (April 2026), PIA $3,000 → $2,112.50/mo. 2027: ``months worked`` = 3, earnings
    $50,000 → excess ($50,000−$24,480)/2 = $12,760. If 2027 were still a grace year only
    the three service months would be charged (3 × $2,112.50 = $6,337.50). Because the
    grace year was used in 2026, the whole $12,760 is charged.
    """
    earn = {2026: 0.0, 2027: 50_000.0}
    months = {2026: 0, 2027: 3}
    grace = ss.initial_grace_year(
        earn,
        ent_start_month_in_year=4,
        start_year=2026,
        exempt_for_year=_exempt_2026,
        months_worked_by_year=months,
        end_year=2027,
    )
    assert grace == 2026

    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(claim=62.0, N_n=28)
    earnings = np.zeros((N_i, N_n))
    earnings[0, 1] = 50_000.0  # 2027 only
    work_months = np.zeros((N_i, N_n), dtype=int)
    work_months[0, 1] = 3
    res = ss.earnings_test(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        work_months_in=work_months,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    monthly = 3000.0 * ss.getSelfFactor(67, 62 + 1 / 12, False)  # 2112.50
    # Grace used up in 2026 → 2027 charges the full excess (not just the 3 service months).
    assert res.withheld_in.sum() == pytest.approx(12_760.0)
    assert res.withheld_in.sum() > 3 * monthly  # more than the grace-year spare would leave


# --------------------------------------------------------------------------------------
# ARF — RS 00615.480 / .482 / .490
# --------------------------------------------------------------------------------------


def test_arf_hand_rates_claim_62_fra_67():
    """404.410 rates: 5/9 of 1% per month for the first 36, 5/12 of 1% beyond.

    Claim at 62 with FRA 67 = 60 reduction months → factor 70%.
    12 crediting months leave 48 → the factor of claiming at 63 (75%).
    """
    assert ss.getSelfFactor(67, 62, False) == pytest.approx(0.70)
    assert ss.getSelfFactor(67, 63, False) == pytest.approx(0.75)
    assert ss.arf_self_factor(67, 62, crediting_months=12, born_on_first=False) == pytest.approx(
        ss.getSelfFactor(67, 63, False)
    )
    assert ss.arf_self_factor(67, 62, crediting_months=12, born_on_first=False) == pytest.approx(0.75)
    # Zero crediting months: unchanged.
    assert ss.arf_self_factor(67, 62, crediting_months=0, born_on_first=False) == pytest.approx(0.70)
    # Claiming at FRA: no ARF.
    assert ss.arf_self_factor(67, 67, crediting_months=12, born_on_first=False) == pytest.approx(1.0)
    # Partial year of crediting months: 6 months → claim 62.5.
    assert ss.arf_self_factor(67, 62, crediting_months=6, born_on_first=False) == pytest.approx(
        ss.getSelfFactor(67, 62.5, False)
    )


def test_arf_partial_deduction_month_counts():
    """RS 00615.482 B.1: full *or partial* work deduction months are crediting months.

    charge_excess_months counts a month with any deduction (including the partial
    last month) in its ``months_with_deduction`` return.
    """
    monthly = [[100.0] * 12]
    withheld, n_ded, partial = ss.charge_excess_months(monthly, 250.0)
    # 2 full months + a partial third → 3 crediting months.
    assert n_ded == 3
    assert partial == 2
    assert withheld[0][2] == pytest.approx(50.0)


def test_arf_spousal_factor_matches_own_rule():
    """RS 00615.482 B.2: a spouse is credited for deductions from their own and the
    worker's work. The spousal factor uses the same crediting-month subtraction.

    Spousal rates (404.410): 25/36 of 1% per month for the first 36, 5/12 of 1% beyond.
    Spousal at 62 with FRA 67 = 65%; at 63 = 70%.
    """
    assert ss.getSpousalFactor(67, 62, False) == pytest.approx(0.65)
    assert ss.arf_spousal_factor(67, 62, crediting_months=12, born_on_first=False) == pytest.approx(0.70)


# --------------------------------------------------------------------------------------
# earnings_test end-to-end properties
# --------------------------------------------------------------------------------------


def _single_worker(pia=3000, claim=62.0, yob=1964, mob=3, tob=15, death_age=89, N_n=28):
    """One worker born 1964-03-15 (FRA 67)."""
    pias = np.array([pia], dtype=np.int32)
    ages = np.array([claim], dtype=np.float64)
    yobs = np.array([yob], dtype=np.int64)
    mobs = np.array([mob], dtype=np.int64)
    tobs = np.array([tob], dtype=np.int64)
    horizons = np.array([min(N_n, death_age)], dtype=np.int64)
    return pias, ages, yobs, mobs, tobs, horizons, 1, N_n


def test_zero_earnings_matches_compute_social_security_benefits():
    """Earnings zero → streams identical to today's (the no-op property)."""
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker()
    base, ages0 = ss.compute_social_security_benefits(
        pias, ages.copy(), yobs, mobs, tobs, horizons, N_i, N_n, thisyear=THISYEAR
    )
    earnings = np.zeros((N_i, N_n))
    res = ss.earnings_test(
        pias,
        ages.copy(),
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert res.zeta_in == pytest.approx(base)
    assert np.all(res.withheld_in == 0)
    assert np.all(res.arf_months == 0)


def test_earliest_claim_follows_owl_rule():
    """compute_social_security_benefits resets 62.0 to 62y1m only for anyone born *after* the 2nd.

    ``tobs <= 2`` is already eligible at 62.0 (born on the 1st or 2nd). The step-0
    prototype started one month earlier than Owl for everyone.
    """
    earnings = np.zeros((1, 28))

    def _ages_for_tob(tob):
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(tob=tob, claim=62.0)
        res = ss.earnings_test(
            pias,
            ages,
            yobs,
            mobs,
            tobs,
            horizons,
            N_i,
            N_n,
            earnings,
            thisyear=THISYEAR,
            exempt_for_year=_exempt_2026,
        )
        return res.ages[0]

    assert _ages_for_tob(15) == pytest.approx(62 + 1 / 12)  # after the 2nd → 62y1m
    assert _ages_for_tob(3) == pytest.approx(62 + 1 / 12)
    assert _ages_for_tob(2) == pytest.approx(62.0)  # on the 2nd → 62.0
    assert _ages_for_tob(1) == pytest.approx(62.0)  # on the 1st → 62.0


def test_nothing_charged_at_or_after_fra():
    """404.435(a)(3) / RS 02501.021 B: the test does not apply at or after FRA."""
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(claim=67.0, N_n=28)
    earnings = np.zeros((N_i, N_n))
    earnings[0, :] = 100_000.0  # works every year
    res = ss.earnings_test(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert np.all(res.withheld_in == 0)
    assert np.all(res.excess_by_year == 0)
    assert np.all(res.arf_months == 0)


def test_nothing_charged_in_fra_year_beyond_the_fra_month():
    """Claim at 62, work through the FRA year: only the pre-FRA months of that year can bite.

    Born 1964-03-15, FRA March 2031. In 2031 the months before March are January and
    February. With $200k, 2031 countable = $200,000×2/12 = $33,333 < $65,160 → FRA-year
    excess 0. So the same hand ARF count as the $100k case: **57** crediting months
    (9 in 2026 + 12×4), nothing from 2031.
    """
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(claim=62.0, N_n=28)
    earnings = np.zeros((N_i, N_n))
    earnings[0, :6] = 200_000.0  # 2026-2031
    res = ss.earnings_test(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert res.excess_by_year[0, :5].sum() > 0
    assert res.excess_by_year[0, 5] == 0  # 2031 FRA year: countable below the exempt amount
    assert res.arf_months[0] == 57


def test_claim_62_while_working_withholds_then_raises_at_fra():
    """Hand pins (claim 62y1m, PIA $3,000, $100k through 2031).

    Born 1964-03-15, claim 62.0 resets to 62y1m (April 2026 entitlement, May-Dec
    checks). Monthly = PIA × getSelfFactor(67, 62y1m) = $3,000 × 0.704167 = **$2,112.50**
    (eight checks in 2026 = $16,900).

    Work $100k/yr 2026-2031, 12 months each:
      excess every full year = ($100,000 − $24,480) / 2 = $37,760 > 12 × $2,112.50,
      so every chargeable month is fully withheld (no carry-over: RS 02501.095 B.1).
      2026: Apr-Dec = 9 months. 2027-2030: 12 each. 2031 FRA year: Jan-Feb only,
      countable $100,000×2/12 = $16,667 < $65,160 → excess 0.
      Crediting months = 9 + 4×12 = **57** (entitlement months are charged and credited,
      not check months).

    ARF from March 2031: factor of claiming at 62y1m + 57/12 = 66y10m
    = getSelfFactor(67, 66y10m) = 0.988889 → $2,966.67/mo.
    """
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(
        pia=3000, claim=62.0, N_n=28
    )
    earnings = np.zeros((N_i, N_n))
    for n in range(6):
        earnings[0, n] = 100_000.0
    work_months = np.full((N_i, N_n), 12)
    work_months[0, 6:] = 0
    res = ss.earnings_test(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        work_months_in=work_months,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    monthly_pre = 3000.0 * ss.getSelfFactor(67, 62 + 1 / 12, False)  # 2112.50
    assert monthly_pre == pytest.approx(2112.50)
    # 57 crediting months, each a full monthly benefit withheld (excess always larger).
    assert res.arf_months[0] == 57
    assert res.withheld_in.sum() == pytest.approx(57 * monthly_pre)
    # From the first full post-FRA year (2032 = plan year 6): 12 months at the ARF factor.
    monthly_post = 3000.0 * ss.getSelfFactor(67, 62 + 1 / 12 + 57 / 12, False)
    assert monthly_post == pytest.approx(2966.6666667)
    assert res.zeta_in[0, 6] == pytest.approx(12 * monthly_post)
    # And that is above the no-test stream at the same claiming age.
    base, _ = ss.compute_social_security_benefits(
        pias,
        np.array([62 + 1 / 12]),
        yobs,
        mobs,
        tobs,
        horizons,
        1,
        N_n,
        thisyear=THISYEAR,
    )
    assert res.zeta_in[0, 6] > base[0, 6]


def test_grace_year_in_end_to_end_claim_july_months_six():
    """Grace-year outcomes pinned (months worked 6 → *nothing* withheld; 12 → withheld).

    Claim 62y4m (July 2026 entitlement). Monthly = $3,000 × getSelfFactor(67, 62y4m)
    = $3,000 × 0.716667 = **$2,150**. 2026 earnings $40,000 → excess ($40,000−$24,480)/2
    = **$7,760**.

    months worked = 6: Jan-Jun work, Jul-Dec non-service in/after entitlement → 2026 is
    the initial grace year (404.435(b)) and the monthly test pays those months in full
    → **withheld 0**.

    months worked = 12: every month is a service month ($3,333/mo > $2,040 monthly
    exempt) → no grace year; the annual test charges from July: 3 full months ($6,450)
    plus $1,310 of the fourth = **$7,760**, all checks in payment year 2026.
    """
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(
        pia=3000, claim=62 + 4 / 12, N_n=28
    )
    earnings = np.zeros((N_i, N_n))
    earnings[0, 0] = 40_000.0  # 2026 only — the plan bullet's "last work year"
    work6 = np.zeros((N_i, N_n), dtype=int)
    work6[0, 0] = 6
    res6 = ss.earnings_test(
        pias,
        ages.copy(),
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        work_months_in=work6,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    work12 = work6.copy()
    work12[0, 0] = 12
    res12 = ss.earnings_test(
        pias,
        ages.copy(),
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        work_months_in=work12,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    monthly = 3000.0 * ss.getSelfFactor(67, 62 + 4 / 12, False)  # 2150
    assert monthly == pytest.approx(2150.0)
    # Plan bullet: months worked = 6 → nothing withheld that year.
    assert res6.withheld_in[0, 0] == 0
    assert res6.withheld_in.sum() == 0
    assert res6.arf_months[0] == 0
    # Plan bullet: months worked = 12 → withheld (hand number $7,760).
    assert res12.withheld_in[0, 0] == pytest.approx(7_760.0)
    assert res12.withheld_in.sum() == pytest.approx(7_760.0)
    # 3 full months + 1 partial = 4 crediting months (RS 00615.482 B.1).
    assert res12.arf_months[0] == 4


def test_withheld_buckets_to_payment_year_not_entitlement_month():
    """The check for entitlement month m is paid in m+1 (Owl's arrears convention).

    Claim 62y1m (April 2026 entitlement), $2,112.50/mo. Earnings chosen so excess
    ($62,504 − $24,480)/2 = $19,012 = 8 full months ($16,900) + $2,112 of the ninth
    (December). The December withholding lands in the January 2027 check → plan year 1.
    """
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(claim=62.0, N_n=28)
    earnings = np.zeros((N_i, N_n))
    earnings[0, 0] = 62_504.0
    res = ss.earnings_test(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    monthly = 3000.0 * ss.getSelfFactor(67, 62 + 1 / 12, False)  # 2112.50
    assert res.withheld_in[0, 0] == pytest.approx(8 * monthly)  # May-Dec 2026 checks
    assert res.withheld_in[0, 1] == pytest.approx(19_012.0 - 8 * monthly)  # Jan 2027 check
    assert res.withheld_in.sum() == pytest.approx(19_012.0)


def test_family_charge_order_and_spousal_arf_crediting():
    """RS 02501.095 B.4 order as *earnings_test* behavior + RS 00615.482 B.2 crediting.

    Couple, no own benefit for person 1 (PIA 0), so the spousal add-on is the whole
    of person 1's check. Both born 1964-06-02 (tob=2 → claim 62.0 is allowed), claim 62.
      own_0 monthly   = $2,000 × 0.70 = **$1,400**
      spousal_1 monthly = $1,000 × 0.65 = **$650**   (unreduced 0.5 × 2000)
      family          = $2,050

    2026 earnings: person 0 $32,680 → excess $4,100 = 2 × $2,050 (two full family
    months); person 1 $27,080 → excess $1,300 = 2 × $650 (two full spouse months).

    Order (B.4): NH's excess first against the family (June, July); then the working
    auxiliary's own excess against what is left of *their* check (August, September).
    A reversed charge would take the spouse's June-July instead — different result.

    Person 1 is reduced in all four months (two from the worker's charge, two from
    their own) → **4** crediting months on person 1's *spouse* record (RS 00615.482
    B.2), **2** on person 0's own record. Person 1 has no own benefit (PIA 0), so 0 on
    their own record: ARFs are granted separately on each record (RS 00615.482 B.3,
    NOTE). Partial-month shares are PIA-based 2:1 (RS 02501.110 examples).
    """
    pias = np.array([2000, 0], dtype=np.int32)
    ages = np.array([62.0, 62.0], dtype=np.float64)
    yobs = np.array([1964, 1964], dtype=np.int64)
    mobs = np.array([6, 6], dtype=np.int64)
    tobs = np.array([2, 2], dtype=np.int64)  # eligible at 62.0
    horizons = np.array([28, 28], dtype=np.int64)
    earnings = np.zeros((2, 28))
    earnings[0, 0] = 32_680.0  # excess 4,100
    earnings[1, 0] = 27_080.0  # excess 1,300
    res = ss.earnings_test(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        2,
        28,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    # Entitlement June 2026 (claim 62, born June). Chargeable Jun-Dec.
    # Person 0 takes June+July of [own_0, spousal_1]; person 1 then Aug+Sep of spousal_1.
    assert res.arf_months[0] == 2
    assert res.arf_months[1] == 0
    assert res.arf_months_spousal[0] == 0
    assert res.arf_months_spousal[1] == 4
    # Person 0 loses only their own June+July.
    assert res.withheld_in[0, :2].sum() == pytest.approx(2 * 1400.0)
    # Person 1 loses spousal June-Sep (two from the family charge, two from their own).
    # Payment year: Jun-Sep ent → Jul-Oct checks, all in 2026 except nothing spills.
    assert res.withheld_in[1, :2].sum() == pytest.approx(4 * 650.0)
    assert res.withheld_in.sum() == pytest.approx(2 * 1400.0 + 4 * 650.0)


def test_family_partial_month_uses_pia_shares():
    """RS 02501.110: a partial family payment is split by original entitlement shares
    (NH 2 / aux 1 in the examples), not by the reduced dollar rates.

    Same couple as the order test, but person 0's excess is $3,075 = 1 full family
    month ($2,050) + $1,025 of the next. The $1,025 paid that month splits 2:1 →
    own_0 $683.33, spousal_1 $341.67. Withheld that month: $716.67 / $308.33.
    """
    pias = np.array([2000, 0], dtype=np.int32)
    ages = np.array([62.0, 62.0], dtype=np.float64)
    yobs = np.array([1964, 1964], dtype=np.int64)
    mobs = np.array([6, 6], dtype=np.int64)
    tobs = np.array([2, 2], dtype=np.int64)
    horizons = np.array([28, 28], dtype=np.int64)
    earnings = np.zeros((2, 28))
    # excess 3,075 = (E − 24,480)/2 → E = 30,630
    earnings[0, 0] = 30_630.0
    res = ss.earnings_test(
        pias,
        ages,
        yobs,
        mobs,
        tobs,
        horizons,
        2,
        28,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    # June full family 2,050; July partial: pay 1,025 split 2:1.
    assert res.withheld_in[0, 0] == pytest.approx(1400.0 + (1400.0 - 1025.0 * 2 / 3))
    assert res.withheld_in[1, 0] == pytest.approx(650.0 + (650.0 - 1025.0 * 1 / 3))
    assert res.withheld_in.sum() == pytest.approx(3_075.0)
    assert res.arf_months[0] == 2  # 1 full + 1 partial
    assert res.arf_months_spousal[1] == 2


def test_survivor_fold_in_and_deferred_arf():
    """Survivor boundary: survivor streams fold in as the greater of own and survivor;
    survivor ARF is deferred (RS 00615.580 not applied).

    Person 0 (PIA $5,000) dies first at plan year 10; person 1 (PIA $1,000) lives to
    year 20, claims at 62 and works 2026-2030 (so they earn ARF crediting months).
    The survivor benefit on person 0's record dwarfs person 1's own, so after the
    first death the stream must be exactly ``compute_survivor_stream`` — *not* raised
    by person 1's crediting months.
    """
    pias = np.array([5000, 1000], dtype=np.int32)
    ages = np.array([62.0, 62.0], dtype=np.float64)
    yobs = np.array([1964, 1964], dtype=np.int64)
    mobs = np.array([6, 6], dtype=np.int64)
    tobs = np.array([15, 15], dtype=np.int64)
    horizons = np.array([10, 20], dtype=np.int64)
    N_i, N_n = 2, 20
    earnings = np.zeros((N_i, N_n))
    earnings[1, :5] = 50_000.0  # person 1 works while person 0 is alive

    surv = ss.compute_survivor_stream(
        pias, ages.copy(), yobs, mobs, tobs, horizons, N_i, N_n, thisyear=THISYEAR
    )
    res = ss.earnings_test(
        pias,
        ages.copy(),
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert res.arf_months[1] > 0
    death_n = surv.death_year_n
    assert death_n < N_n
    # Greater-of fold-in uses the *un-ARF* survivor stream (survivor ARF not modeled).
    assert res.zeta_in[1, death_n:] == pytest.approx(surv.annual[death_n:])
    assert res.zeta_in[1, death_n] > 0


def test_zero_earnings_couple_with_survivor_matches_today():
    """No-op on a couple with a survivor period: identical to compute_social_security_benefits."""
    pias = np.array([3000, 2000], dtype=np.int32)
    ages = np.array([67.0, 65.0], dtype=np.float64)
    yobs = np.array([1964, 1966], dtype=np.int64)
    mobs = np.array([6, 6], dtype=np.int64)
    tobs = np.array([15, 15], dtype=np.int64)
    horizons = np.array([12, 22], dtype=np.int64)
    N_i, N_n = 2, 22
    base, _ = ss.compute_social_security_benefits(
        pias, ages.copy(), yobs, mobs, tobs, horizons, N_i, N_n, thisyear=THISYEAR
    )
    res = ss.earnings_test(
        pias,
        ages.copy(),
        yobs,
        mobs,
        tobs,
        horizons,
        N_i,
        N_n,
        np.zeros((N_i, N_n)),
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert res.zeta_in == pytest.approx(base)
    assert np.all(res.arf_months == 0)


def test_exempt_amounts_table_projection():
    """RS 02501.025 D: 2024-2026 chart, 2027 from 91 FR 67380; later years held at the last
    known nominal amount."""
    a26 = ss.get_exempt_amounts(2026)
    assert a26.annual == pytest.approx(24_480.0)
    assert a26.annual_fra == pytest.approx(65_160.0)
    assert a26.monthly == pytest.approx(2_040.0)
    assert a26.monthly_fra == pytest.approx(5_430.0)

    a25 = ss.get_exempt_amounts(2025)
    assert a25.annual == pytest.approx(23_400.0)
    assert a25.annual_fra == pytest.approx(62_160.0)
    assert a25.monthly == pytest.approx(1_950.0)
    assert a25.monthly_fra == pytest.approx(5_180.0)

    a24 = ss.get_exempt_amounts(2024)
    assert a24.annual == pytest.approx(22_320.0)
    assert a24.annual_fra == pytest.approx(59_520.0)
    assert a24.monthly == pytest.approx(1_860.0)
    assert a24.monthly_fra == pytest.approx(4_960.0)

    a27 = ss.get_exempt_amounts(2027)
    assert a27.annual == pytest.approx(25_560.0)
    assert a27.annual_fra == pytest.approx(67_920.0)
    assert a27.monthly == pytest.approx(2_130.0)
    assert a27.monthly_fra == pytest.approx(5_660.0)

    # Projection: later years hold the last known nominal amount.
    a30 = ss.get_exempt_amounts(2030)
    assert a30.annual == pytest.approx(25_560.0)
    assert a30.monthly == pytest.approx(2_130.0)


def test_plan_exempt_amounts_are_deflated_not_reinflated():
    """#231: a plan in 2026 dollars reads 2027's published amount deflated by 2027's factor, and
    holds it flat in real terms after; a plan starting in 2027 reads it as its own dollars; one
    starting after the table takes the last amount as its first year's dollars (a floor)."""
    g = np.array([1.0, 1.025, 1.025**2, 1.025**3])
    e26 = ss.plan_exempt_for_year(2026, g, 3)
    assert e26(2026).annual == pytest.approx(24_480.0)
    assert e26(2027).annual == pytest.approx(25_560.0 / 1.025)
    assert e26(2028).annual_fra == pytest.approx(67_920.0 / 1.025)
    assert e26(2025).annual == pytest.approx(23_400.0)  # before the plan: nominal
    e27 = ss.plan_exempt_for_year(2027, g, 3)
    assert e27(2027).annual == pytest.approx(25_560.0)
    assert e27(2029).annual == pytest.approx(25_560.0)
    e30 = ss.plan_exempt_for_year(2030, g, 3)
    assert e30(2030).annual == pytest.approx(25_560.0)


# --------------------------------------------------------------------------------------
# Edge cases: plan start, charge order, records, survivors, FRA month
# --------------------------------------------------------------------------------------


def _both(pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, earnings=None, **kw):
    """Run today's ``compute_social_security_benefits`` and ``earnings_test`` on one case."""
    args = (
        np.array(pias, dtype=np.int32),
        np.array(ages, dtype=np.float64),
        np.array(yobs, dtype=np.int64),
        np.array(mobs, dtype=np.int64),
        np.array(tobs, dtype=np.int64),
        np.array(horizons, dtype=np.int64),
        N_i,
        N_n,
    )
    base, _ = ss.compute_social_security_benefits(*args[:1], args[1].copy(), *args[2:], thisyear=THISYEAR, **kw)
    if earnings is None:
        earnings = np.zeros((N_i, N_n))
    res = ss.earnings_test(
        *args[:1], args[1].copy(), *args[2:], earnings, thisyear=THISYEAR, exempt_for_year=_exempt_2026, **kw
    )
    return base, res


def _noop_cases():
    """Zero-earnings cases covering what the first no-op tests missed: claims before the
    plan starts (own and spousal), a trim with a survivor period, a survivor who claims
    the survivor benefit later than the first death, birthdays on the 1st/2nd."""
    cases = []
    for yob, mob, tob, claim in [
        (1961, 1, 15, 62.0),  # claimed 2023: Jamie in alex+jamie
        (1960, 12, 15, 62.0),  # entitlement Dec 2022 + 1 month
        (1963, 12, 15, 62.0),  # entitlement Jan 2026: first check Feb 2026
        (1963, 11, 15, 62.0),  # entitlement Dec 2025: first check Jan 2026
        (1964, 3, 1, 62.0),
        (1964, 3, 2, 63.5),
        (1958, 7, 15, 67.0),
        (1964, 6, 15, 70.0),
    ]:
        cases.append(([2400], [claim], [yob], [mob], [tob], [25], 1, 25, {}))
    for kw in [{}, {"trim_pct": 20, "trim_year": 2035}, {"survivor_claim_age": "FRA"},
               {"survivor_claim_age": 70}, {"trim_pct": 23, "trim_year": 2027, "survivor_claim_age": 65}]:
        # Spousal add-on for person 1 (0.5 x 3000 > 800), both already collecting.
        cases.append(([3000, 800], [62.0, 62.0], [1961, 1962], [1, 5], [15, 15], [9, 22], 2, 22, kw))
        # Spousal add-on, younger spouse, first death before the survivor's FRA.
        cases.append(([3000, 800], [64.0, 62.0], [1962, 1967], [4, 9], [15, 15], [5, 25], 2, 25, kw))
        # Survivor's own benefit larger than the survivor benefit.
        cases.append(([1200, 2600], [67.0, 70.0], [1964, 1965], [6, 2], [15, 1], [12, 24], 2, 24, kw))
    # Spousal add-on on top of an own benefit with delayed credits: the credits come out of the
    # excess (upstream #211, merged 2026-10-22); without the builder's mirror it pays $2,880/yr more.
    cases.append(([3000, 1000], [62.0, 70.0], [1962, 1964], [6, 3], [15, 15], [30, 30], 2, 30, {}))
    return cases


@pytest.mark.parametrize("case", _noop_cases())
def test_zero_earnings_matches_today_on_a_grid(case):
    """No-op property on a grid: zero earnings → exactly ``compute_social_security_benefits``.

    Covers a claim before the plan start (its January check) and a trim with survivor
    years (applied once).
    """
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, kw = case
    base, res = _both(pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, **kw)
    assert res.zeta_in == pytest.approx(base, abs=1e-6)
    assert np.all(res.withheld_in == 0)
    assert np.all(res.arf_months == 0)
    assert np.all(res.arf_months_spousal == 0)


def _order_couple(worker_index):
    """The order-test couple at 40k / 40k, with the worker at ``worker_index``."""
    pias = [2000, 0]
    earnings = np.zeros((2, 28))
    earnings[:, 0] = 40_000.0  # excess (40,000 - 24,480)/2 = 7,760 each
    if worker_index == 1:
        pias = pias[::-1]
    res = ss.earnings_test(
        np.array(pias, dtype=np.int32),
        np.array([62.0, 62.0]),
        np.array([1964, 1964], dtype=np.int64),
        np.array([6, 6], dtype=np.int64),
        np.array([2, 2], dtype=np.int64),
        np.array([28, 28], dtype=np.int64),
        2,
        28,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    w, a = worker_index, 1 - worker_index
    return res, w, a


@pytest.mark.parametrize("worker_index", [0, 1])
def test_charge_order_does_not_depend_on_person_index(worker_index):
    """RS 02501.095: the worker's excess is charged first, whichever person is listed first.

    Entitlement June-December 2026; family $2,050 (own $1,400 +
    spousal $650). Worker's excess $7,760: June-August in full ($6,150), then $1,610 of
    September; the $440 paid that month splits 2:1 (RS 02501.110) → own $293.33,
    spousal $146.67. Then the auxiliary's own $7,760 against what is left of their
    check: September's $146.67 and October-December ($1,950) → all of it.
      worker withheld  3 x 1,400 + (1,400 - 293.33) = **$5,306.67**, 4 crediting months
      aux withheld     7 x 650                        = **$4,550.00**, 7 (spouse record)
    """
    res, w, a = _order_couple(worker_index)
    assert res.withheld_in[w].sum() == pytest.approx(3 * 1400.0 + 1400.0 - 440.0 * 2 / 3)
    assert res.withheld_in[a].sum() == pytest.approx(7 * 650.0)
    assert res.arf_months[w] == 4
    assert res.arf_months_spousal[a] == 7
    assert res.arf_months[a] == 0


def _dual_couple(ages, earnings):
    return ss.earnings_test(
        np.array([3000, 1000], dtype=np.int32),
        np.array(ages, dtype=np.float64),
        np.array([1964, 1964], dtype=np.int64),
        np.array([6, 6], dtype=np.int64),
        np.array([15, 15], dtype=np.int64),
        np.array([28, 28], dtype=np.int64),
        2,
        28,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )


def test_dual_entitled_own_record_not_credited_for_worker_charge():
    """RS 00615.482 B.3 NOTE: "grant ARFs separately on each record".

    Worker PIA $3,000, auxiliary PIA $1,000 (spousal add-on $500), both born 1964-06-15
    and claiming at 62 → 62y1m (July 2026). Only the worker works, $80,000 in 2026-2028:
    excess $27,760 a year against a family of $2,112.50 (0.704167 x 3,000) + $327.08
    (0.654167 x 500) = $2,439.58: July-December 2026 (6), then 11 full months and a
    partial December in 2027 and 2028 (12 + 12) → **30** months on the worker's record,
    and the auxiliary's *spouse* record. The auxiliary's own benefit was never reduced,
    so **0** months on their own record.

    From 2032 (all checks after the June 2031 FRA) the auxiliary is paid
      own     1,000 x 0.704167 (62y1m, unadjusted)              = 704.17
      spousal   500 x (1 - (1/12) x 29/12) = 500 x 0.798611      = 399.31  (64y7m)
    """
    earnings = np.zeros((2, 28))
    earnings[0, :3] = 80_000.0
    res = _dual_couple([62.0, 62.0], earnings)
    assert res.arf_months[0] == 30
    assert res.arf_months_spousal[1] == 30
    assert res.arf_months[1] == 0
    own = 1000 * (0.8 - 0.05 * 23 / 12)
    spousal = 500 * (1 - 29 / 144)
    assert res.zeta_in[1, 6] == pytest.approx(12 * (own + spousal))


def test_spousal_record_not_credited_before_spousal_entitlement():
    """Months withheld from the auxiliary's own benefit before the spousal benefit starts
    do not reduce the spousal reduction (RS 00615.482 B.2-B.3).

    Auxiliary PIA $800 claims at 62 → 62y1m (July 2026) and works $60,000 in 2026-2027:
    excess $17,760 a year against $563.33 a month → July-December 2026 and all of 2027
    withheld: **18** months on their own record. The worker (PIA $3,000) claims at 66
    (June 2030), so the spousal add-on ($700) starts then, at the auxiliary's age 66,
    with no deduction ever: **0** months on the spouse record.

    From 2032 the auxiliary is paid
      own     800 x factor at 62y1m + 18 months = 63y7m = 800 x 0.779167 = 623.33
      spousal 700 x factor at 66 = 700 x (1 - 1/12)                      = 641.67
    """
    earnings = np.zeros((2, 28))
    earnings[1, :2] = 60_000.0
    res = ss.earnings_test(
        np.array([3000, 800], dtype=np.int32),
        np.array([66.0, 62.0]),
        np.array([1964, 1964], dtype=np.int64),
        np.array([6, 6], dtype=np.int64),
        np.array([15, 15], dtype=np.int64),
        np.array([28, 28], dtype=np.int64),
        2,
        28,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert res.arf_months[1] == 18
    assert res.arf_months_spousal[1] == 0
    own = 800 * (0.8 - 0.05 * 5 / 12)
    spousal = 700 * (1 - 1 / 12)
    assert res.zeta_in[1, 6] == pytest.approx(12 * (own + spousal))


def test_survivor_years_are_not_charged():
    """The test is not applied to checks paid from the first death on
    (survivor benefits under the test are not modeled; module docstring). What is paid
    there is today's stream, and nothing is reported as withheld.

    Person 0 dies first (plan year 3, 2029); person 1 (born 1965-06, under FRA until
    2032) earns $100,000 in 2029-2031.
    """
    earnings = np.zeros((2, 20))
    earnings[1, 3:6] = 100_000.0
    base, res = _both([5000, 1000], [62.0, 62.0], [1964, 1965], [6, 6], [15, 15], [3, 20], 2, 20, earnings)
    assert np.all(res.withheld_in[1, 3:] == 0)
    assert res.zeta_in[1, 3:] == pytest.approx(base[1, 3:])


def test_survivor_base_uses_deceased_arf_after_their_fra():
    """The widow(er)'s benefit is based on the deceased's benefit at death (CFR 404.338),
    which includes the ARF when death comes after the deceased's FRA.

    Deceased: PIA $3,000, born 1964-06-15, claims 62 → 62y1m (July 2026), earns $100,000
    in 2026-2030: every month to the end of 2030 withheld (excess $37,760 a year) → 6 +
    48 = **54** crediting months; at FRA (June 2031) the factor is that of 62y1m + 54
    months = 66y7m, 5 months early: 1 - 5 x 5/9 % = 0.972222, i.e. $2,916.67 a month.
    Death in 2046 (plan year 20). The survivor (PIA $1,000, same birth date) is past
    their survivor FRA then, so the survivor benefit is the full
    $2,916.67 x 12 = **$35,000** a year (not max($2,112.50, 0.825 x 3,000) x 12 = $29,700).
    """
    earnings = np.zeros((2, 30))
    earnings[0, :5] = 100_000.0
    base, res = _both([3000, 1000], [62.0, 62.0], [1964, 1964], [6, 6], [15, 15], [20, 30], 2, 30, earnings)
    assert res.arf_months[0] == 54
    assert res.zeta_in[1, 20:] == pytest.approx(35_000.0)
    assert base[1, 20:] == pytest.approx(29_700.0)


def test_survivor_base_without_arf_when_death_precedes_deceased_fra():
    """Death before the deceased's FRA: the ARF has not happened, so the survivor
    benefit is today's (same couple, deceased's horizon ends in 2029)."""
    earnings = np.zeros((2, 30))
    earnings[0, :4] = 100_000.0
    base, res = _both([3000, 1000], [62.0, 62.0], [1964, 1964], [6, 6], [15, 15], [4, 30], 2, 30, earnings)
    assert res.zeta_in[1, 4:] == pytest.approx(base[1, 4:])


def test_fra_year_monthly_exempt_is_the_fra_amount():
    """RS 02501.025 B.2: the monthly exempt amount is 1/12 of the *applicable* annual
    amount, $65,160 / 12 = $5,430 in the FRA year. And a non-service
    month must be before FRA (RS 02501.030; 404.435(a)(7)).

    FRA June 2031, entitlement January 2031.
    - $3,000 a month all year: January-May are non-service months under $5,430 → 2031 is
      the initial grace year (under $2,040 none would be, and June-December, at or after
      FRA, never count).
    - $10,000 a month for 5 months: January-May are service months; June-December have
      no work but are at or after FRA → no grace year.
    """
    exempt = _exempt_2026
    assert ss.initial_grace_year(
        {2031: 36_000.0}, 1, 2031, exempt, {2031: 12}, end_year=2031, fra_year=2031, fra_month_in_year=6
    ) == 2031
    assert ss.initial_grace_year(
        {2031: 50_000.0}, 1, 2031, exempt, {2031: 5}, end_year=2031, fra_year=2031, fra_month_in_year=6
    ) is None


def test_arf_never_exceeds_full_benefit_born_on_first():
    """Someone born on the 1st attains FRA a month earlier in calendar
    terms; crediting months bring the factor up to 1.0 and never past it."""
    # Born on the 1st, conventional 62 = SSA 62y1m: 59 reduction months.
    assert ss.arf_self_factor(67, 62.0, 59, True) == pytest.approx(1.0)
    assert ss.arf_self_factor(67, 62.0, 60, True) == pytest.approx(1.0)
    assert ss.arf_spousal_factor(67, 62.0, 60, True) == pytest.approx(1.0)


def test_born_on_first_fra_month_is_not_charged():
    """Born 1964-03-01: attains 67 on 2031-02-28, so the FRA month is February 2031 and
    only January's earnings count in 2031 (RS 02501.021 B; 404.430(b)).

    $600,000 a year 2026-2031: March 2026 - December 2030 all withheld (10 + 48 = **58**
    crediting months); 2031 countable = $50,000 < $65,160 → no excess. Reduction months
    at conventional 62 (SSA 62y1m) are 59, so 1 is left at FRA: factor 1 - 5/9 % =
    0.994444, $2,983.33 a month, **$35,800** a year from 2032.
    """
    earnings = np.zeros((1, 28))
    earnings[0, :6] = 600_000.0
    res = ss.earnings_test(
        np.array([3000], dtype=np.int32),
        np.array([62.0]),
        np.array([1964], dtype=np.int64),
        np.array([3], dtype=np.int64),
        np.array([1], dtype=np.int64),
        np.array([28], dtype=np.int64),
        1,
        28,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert res.excess_by_year[0, 5] == 0
    assert res.arf_months[0] == 58
    assert res.zeta_in[0, 6] == pytest.approx(12 * 3000 * (1 - 1 / 180))


# --------------------------------------------------------------------------------------
# Inputs and records
# --------------------------------------------------------------------------------------


def test_zero_months_with_earnings_means_twelve():
    """``months worked`` 0 in a year with earnings means "not given" (12), as on the
    plan side: otherwise ``countable_earnings`` would count nothing and the year would
    go untested. Same worker and earnings as the $40,000 / 12 months case."""
    pias, ages, yobs, mobs, tobs, horizons, N_i, N_n = _single_worker(claim=62.0, N_n=28)
    earnings = np.zeros((1, 28))
    earnings[0, :3] = 40_000.0
    months_zero = np.zeros((1, 28))
    months_twelve = np.where(earnings > 0, 12, 0)
    runs = [
        ss.earnings_test(pias, ages.copy(), yobs, mobs, tobs, horizons, N_i, N_n, earnings, work_months_in=m,
                         thisyear=THISYEAR, exempt_for_year=_exempt_2026)
        for m in (months_zero, months_twelve)
    ]
    assert runs[0].withheld_in.sum() > 0
    assert runs[0].withheld_in == pytest.approx(runs[1].withheld_in)
    assert runs[0].arf_months[0] == runs[1].arf_months[0]


def test_spousal_crediting_months_stop_at_the_auxiliarys_fra():
    """The ARF is computed at FRA from the reduction months before it (RS 00615.482):
    deductions from the spousal add-on after the auxiliary's FRA are still withheld but
    are not crediting months.

    Auxiliary: PIA $800, born 1962-06-15 (FRA June 2029), claims own at 62y1m (July 2024),
    never works. Worker: PIA $3,000, born 1966-06-15, claims 62y1m (July 2028), so the
    spousal add-on ($700) starts July 2028 at the auxiliary's 66y1m, factor 1 - (1/12) x
    11/12 = 0.923611 ($646.53). The worker earns $40,000 in 2028-2032: excess $7,760 a year
    against a family of $2,112.50 + $646.53 = $2,759.03, so about 2.8 months a year, from
    the first chargeable month: July-September 2028 and January-March 2029 are before the
    auxiliary's FRA → **6** crediting months (2030-2032's are after it). From FRA the
    spousal factor is that of 66y1m + 6 months = 66y7m: 1 - (1/12) x 5/12 = 0.965278.
    In 2034 (no work, all checks after FRA) the auxiliary is paid
      12 x (800 x 0.704167 + 700 x 0.965278) = 12 x (563.33 + 675.69) = 14,868.25
    """
    N = 20
    earnings = np.zeros((2, N))
    earnings[1, 2:7] = 40_000.0
    res = ss.earnings_test(
        np.array([800, 3000], dtype=np.int32),
        np.array([62.0, 62.0]),
        np.array([1962, 1966], dtype=np.int64),
        np.array([6, 6], dtype=np.int64),
        np.array([15, 15], dtype=np.int64),
        np.array([N, N], dtype=np.int64),
        2,
        N,
        earnings,
        thisyear=THISYEAR,
        exempt_for_year=_exempt_2026,
    )
    assert res.arf_months_spousal[0] == 6
    assert res.arf_months[0] == 0
    own = 800 * (0.8 - 0.05 * 23 / 12)
    spousal = 700 * (1 - 5 / 144)
    assert res.zeta_in[0, 8] == pytest.approx(12 * (own + spousal))


@pytest.mark.parametrize("wage, arf_sp", [(60_000.0, 26), (70_000.0, 32)])
def test_worker_charge_after_spouse_fra_is_at_the_adjusted_add_on(wage, arf_sp):
    """#232: the spouse's add-on from their FRA month is the ARF-adjusted one (404.412(b)), and a
    worker still under FRA charges against it (403(b)(1)). Charged at the pre-ARF rate and scaled
    after, dollars went missing: in payment year 2029, where the worker's excess is used up, the
    household's paid + withheld now equals the benefits due. Worker born 1963-08, PIA \\$2,400 at
    62y1m, earning 2026-2030; spouse born 1962-03 (FRA March 2029), PIA \\$400 at 63y10m."""
    N_n = 8
    kw = dict(pias=[2400, 400], ages=[62 + 1 / 12, 63 + 10 / 12], yobs=[1963, 1962], mobs=[8, 3], tobs=[15, 15],
              horizons=[N_n, N_n], N_i=2, N_n=N_n, thisyear=THISYEAR, exempt_for_year=_exempt_2026)
    earnings = np.zeros((2, N_n))
    earnings[0, :5] = wage
    res = ss.earnings_test(earnings_in=earnings, **kw)
    base = ss.earnings_test(earnings_in=np.zeros((2, N_n)), **kw)
    assert res.arf_months_spousal[1] == arf_sp  # crediting months: before FRA, as before the fix

    n = 2029 - THISYEAR
    fra = float(ss.getFRAs(np.array([1962]), np.array([3]), np.array([15]))[0])
    old = ss.getSpousalFactor(fra, 63 + 10 / 12, False)
    new = ss.arf_spousal_factor(fra, 63 + 10 / 12, arf_sp, False)
    add_on = ss.getSpousalBenefits(np.array([2400, 400]))[1] * old
    # Payment year 2029: checks for December 2028 to November 2029, nine of them from FRA.
    due = base.zeta_in[:, n].sum() + 9 * add_on * (new / old - 1)
    assert res.excess_by_year[0, n] < due  # the excess is used up within the year
    assert res.withheld_in[:, n].sum() == pytest.approx(res.excess_by_year[0, n])
    assert res.zeta_in[:, n].sum() + res.withheld_in[:, n].sum() == pytest.approx(due, abs=0.01)


# --------------------------------------------------------------------------------------
# Years before the plan (#235): PIA $2,000 claimed July 2025 at 62y1m ($1,408.33 a month),
# plan starting in 2026.
# --------------------------------------------------------------------------------------


def _claimed_in_2025(earn_2026, months_2026, earn_2025=None):
    N = 10
    e = np.zeros((1, N))
    m = np.zeros((1, N))
    e[0, 0], m[0, 0] = earn_2026, months_2026
    past = None if earn_2025 is None else np.array([[0, 0, 0, 0, earn_2025]], dtype=float)
    past_m = None if earn_2025 is None else np.array([[0, 0, 0, 0, 12]], dtype=float)
    return ss.earnings_test([2000], [62 + 1 / 12], [1963], [6], [15], [N], 1, N, e, work_months_in=m,
                            thisyear=2026, past_earnings_in=past, past_work_months_in=past_m)


def test_grace_year_not_used_before_the_plan():
    """$5,000 every month of 2025, then January-June 2026 for $80,000. No month of 2025 was a
    non-service month, so 2026 is the initial grace year (404.435(b)(1)): its five checks for
    July-November are paid in 2026; the December 2025 check and January-June are withheld."""
    r = _claimed_in_2025(80_000, 6, earn_2025=60_000)
    assert r.zeta_in[0, 0] == pytest.approx(5 * 1408.33, abs=0.1)
    assert r.zeta_in[0, 1] == pytest.approx(12 * 1408.33, abs=0.1)
    # July 2025 - June 2026 are left out of the reduction period at FRA.
    assert r.arf_months[0] == 12
    # Without the past year, 2025 is taken as the grace year and 2026 gets the annual test.
    assert _claimed_in_2025(80_000, 6).zeta_in[0, 0] == pytest.approx(1408.33, abs=0.1)


def test_months_withheld_before_the_plan_count_toward_the_arf():
    """$5,000 every month of 2025 and no work from 2026: July-December 2025 are withheld,
    the December check among them (paid in January 2026), and credited at FRA in June 2030
    (402(q)(7)(A)): $1,458.33 a month from then on instead of $1,408.33."""
    r = _claimed_in_2025(0, 0, earn_2025=60_000)
    assert r.arf_months[0] == 6
    assert r.zeta_in[0, 0] == pytest.approx(11 * 1408.33, abs=0.1)
    # Paid in 2030: the checks for December 2029 - May 2030, then six from June.
    assert r.zeta_in[0, 4] == pytest.approx(6 * 1408.33 + 6 * 1458.33, abs=0.1)
    assert r.zeta_in[0, 5] == pytest.approx(12 * 1458.33, abs=0.1)


def test_years_before_the_plan_without_earnings_change_nothing():
    a = _claimed_in_2025(80_000, 6)
    b = _claimed_in_2025(80_000, 6, earn_2025=0)
    np.testing.assert_array_equal(a.zeta_in, b.zeta_in)
    np.testing.assert_array_equal(a.withheld_in, b.withheld_in)
    np.testing.assert_array_equal(a.arf_months, b.arf_months)
