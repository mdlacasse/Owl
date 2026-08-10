"""
Tests for socialsecurity module - Social Security benefit calculations.

Tests verify Social Security rules including full retirement age calculations
and benefit computations.

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

import pytest
import numpy as np

from owlplanner import socialsecurity as ss


# Helper: mobs/tobs for year-only FRA (not Jan 1, so no boundary effect)
_M = [6]
_T = [15]


def test_FRA():
    years = range(1954, 1960)
    for i, y in enumerate(years):
        yfra = ss.getFRAs([y], _M, _T)
        assert yfra[0] % 1 == pytest.approx(2 * i / 12)

    yfra = ss.getFRAs([1940], _M, _T)
    assert yfra[0] == pytest.approx(65.5)
    yfra = ss.getFRAs([1938], _M, _T)
    assert yfra[0] == pytest.approx(65 + 2 / 12)
    yfra = ss.getFRAs([1942], _M, _T)
    assert yfra[0] == pytest.approx(65 + 10 / 12)
    yfra = ss.getFRAs([1943], _M, _T)
    assert yfra[0] == pytest.approx(66)
    yfra = ss.getFRAs([1937], _M, _T)
    assert yfra[0] == pytest.approx(65)
    yfra = ss.getFRAs([1900], _M, _T)
    assert yfra[0] == pytest.approx(65)
    yfra = ss.getFRAs([1954], _M, _T)
    assert yfra[0] == 66
    yfra = ss.getFRAs([1960], _M, _T)
    assert yfra[0] == 67
    yfra = ss.getFRAs([1969], _M, _T)
    assert yfra[0] == 67

    # Jan 1 special case (POMS: born 1/1 gets prior year's FRA)
    yfra = ss.getFRAs([1960], [1], [1])
    assert yfra[0] == pytest.approx(66 + 10 / 12)
    yfra = ss.getFRAs([1960], [6], [15])
    assert yfra[0] == 67
    yfra = ss.getSurvivorFRAs([1962], [1], [1])
    assert yfra[0] == pytest.approx(66 + 10 / 12)
    yfra = ss.getSurvivorFRAs([1962], [7], [4])
    assert yfra[0] == 67


def test_selfFactor():
    ages = range(62, 71)
    factors66 = [0.75, 0.80, 0.866667, 0.9333333, 1.0, 1.08, 1.16, 1.24, 1.32]
    factors67 = [0.70, 0.75, 0.80, 0.866667, 0.9333333, 1.0, 1.08, 1.16, 1.24]
    for i, a in enumerate(ages):
        assert ss.getSelfFactor(66, a, False) == pytest.approx(factors66[i], 0.001)
        assert ss.getSelfFactor(67, a, False) == pytest.approx(factors67[i], 0.001)
        if a > 62:
            assert ss.getSelfFactor(66, a - 1 / 12, True) == pytest.approx(factors66[i], 0.001)
            assert ss.getSelfFactor(67, a - 1 / 12, True) == pytest.approx(factors67[i], 0.001)

    # Example from SSA: https://www.ssa.gov/benefits/retirement/planner/1955-delay.html
    assert ss.getSelfFactor(66 + 2 / 12, 66 + 2 / 12, False) == pytest.approx(1.00, 0.001)
    assert ss.getSelfFactor(66 + 2 / 12, 67, False) == pytest.approx(1.06667, 0.001)
    assert ss.getSelfFactor(66 + 2 / 12, 68, False) == pytest.approx(1.14667, 0.001)
    assert ss.getSelfFactor(66 + 2 / 12, 69, False) == pytest.approx(1.22667, 0.001)
    assert ss.getSelfFactor(66 + 3 / 12, 69 + 1 / 12, False) == pytest.approx(1.22667, 0.001)
    assert ss.getSelfFactor(66 + 2 / 12, 70, False) == pytest.approx(1.30667, 0.001)


def test_spousalFactor():
    ages = range(62, 71)
    factors66 = [0.70, 0.75, 0.833333, 0.9166667, 1.0, 1.0, 1.0, 1.0, 1.0]
    factors67 = [0.65, 0.70, 0.75, 0.833333, 0.9166667, 1.0, 1.0, 1.0, 1.0]
    for i, a in enumerate(ages):
        assert ss.getSpousalFactor(66, a, False) == pytest.approx(factors66[i], 0.001)
        assert ss.getSpousalFactor(67, a, False) == pytest.approx(factors67[i], 0.001)
        if a > 62:
            assert ss.getSpousalFactor(66, a - 1 / 12, True) == pytest.approx(factors66[i], 0.001)
            assert ss.getSpousalFactor(67, a - 1 / 12, True) == pytest.approx(factors67[i], 0.001)

    # Individual born in 1955.
    assert ss.getSpousalFactor(66 + 2 / 12, 66 + 2 / 12, False) == pytest.approx(1.00, 0.001)
    assert ss.getSpousalFactor(66 + 2 / 12, 66, False) == pytest.approx(2 * 0.4931, 0.001)
    assert ss.getSpousalFactor(66 + 2 / 12, 65, False) == pytest.approx(2 * 0.4514, 0.001)
    assert ss.getSpousalFactor(66 + 2 / 12, 64, False) == pytest.approx(2 * 0.4097, 0.001)
    assert ss.getSpousalFactor(66 + 2 / 12, 63, False) == pytest.approx(2 * 0.3708, 0.001)
    assert ss.getSpousalFactor(66 + 2 / 12, 62, False) == pytest.approx(2 * 0.3458, 0.001)


def test_SpousalBenefits():
    pias = [2800]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [0])

    pias = [2800, 1400]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [0, 0])

    pias = [2800, 1000]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [0, 400])

    pias = [1000, 3000]
    benefits = ss.getSpousalBenefits(pias)
    assert np.array_equal(benefits, [500, 0])


def test_compute_social_security_benefits_single():
    """Single individual: zeta_in has correct shape and non-zero where expected."""
    from datetime import date

    thisyear = date.today().year
    yob = thisyear - 67  # 67 years old now
    pias = np.array([2000])
    ages = np.array([67.0])
    yobs = np.array([yob])
    mobs = np.array([1])
    tobs = np.array([15])
    horizons = np.array([20])
    N_i, N_n = 1, 20

    zeta_in, ages_out = ss.compute_social_security_benefits(pias, ages, yobs, mobs, tobs, horizons, N_i, N_n)
    assert zeta_in.shape == (1, 20)
    # SS starts at 67, paid in arrears; year 0 should have partial, years 1-19 full
    assert np.sum(zeta_in) > 0
    assert np.array_equal(ages_out, ages)


def test_compute_social_security_benefits_couple():
    """Two individuals: zeta_in has correct shape."""
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([thisyear - 66, thisyear - 63])
    pias = np.array([2333, 2083])
    ages = np.array([67.0, 70.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 16])
    horizons = np.array([20, 20])
    N_i, N_n = 2, 20

    zeta_in, ages_out = ss.compute_social_security_benefits(pias, ages, yobs, mobs, tobs, horizons, N_i, N_n)
    assert zeta_in.shape == (2, 20)
    assert np.sum(zeta_in) > 0


def test_compute_social_security_benefits_age_reset():
    """Claiming age below 62 is reset to 62."""
    from datetime import date

    thisyear = date.today().year
    yob = thisyear - 60  # 60 years old
    pias = np.array([2000])
    ages = np.array([60.0])  # Invalid: before 62
    yobs = np.array([yob])
    mobs = np.array([1])
    tobs = np.array([1])  # born on 1st: eligible at 62
    horizons = np.array([20])
    N_i, N_n = 1, 20

    zeta_in, ages_out = ss.compute_social_security_benefits(pias, ages, yobs, mobs, tobs, horizons, N_i, N_n)
    assert ages_out[0] == pytest.approx(62.0)
    assert ages[0] == pytest.approx(60.0)  # Original unchanged (we copy)


def test_survivor_FRA():
    """Verify survivor FRA schedule matches SSA table (distinct from retirement FRA)."""
    assert ss.getSurvivorFRAs([1939], _M, _T)[0] == pytest.approx(65)
    assert ss.getSurvivorFRAs([1900], _M, _T)[0] == pytest.approx(65)
    assert ss.getSurvivorFRAs([1940], _M, _T)[0] == pytest.approx(65 + 2 / 12)
    assert ss.getSurvivorFRAs([1944], _M, _T)[0] == pytest.approx(65 + 10 / 12)
    assert ss.getSurvivorFRAs([1945], _M, _T)[0] == pytest.approx(66)
    assert ss.getSurvivorFRAs([1956], _M, _T)[0] == pytest.approx(66)
    assert ss.getSurvivorFRAs([1957], _M, _T)[0] == pytest.approx(66 + 2 / 12)
    assert ss.getSurvivorFRAs([1961], _M, _T)[0] == pytest.approx(66 + 10 / 12)
    assert ss.getSurvivorFRAs([1962], _M, _T)[0] == pytest.approx(67)
    assert ss.getSurvivorFRAs([2000], _M, _T)[0] == pytest.approx(67)
    # Two-month-per-year increments in each transitional band.
    for i, y in enumerate(range(1940, 1945)):
        assert ss.getSurvivorFRAs([y], _M, _T)[0] % 1 == pytest.approx(2 * (i + 1) / 12)
    for i, y in enumerate(range(1957, 1962)):
        assert ss.getSurvivorFRAs([y], _M, _T)[0] % 1 == pytest.approx(2 * (i + 1) / 12)


def test_survivor_factor():
    """Verify survivor factor: 1.0 at FRA, 0.715 at 60, linear in between."""
    # At or above survivor FRA: full benefit.
    assert ss._survivor_factor(66, 66) == pytest.approx(1.0)
    assert ss._survivor_factor(66, 70) == pytest.approx(1.0)
    assert ss._survivor_factor(67, 67) == pytest.approx(1.0)
    # At age 60 (minimum survivor age): always 71.5%, regardless of survivor FRA.
    assert ss._survivor_factor(66, 60) == pytest.approx(0.715)
    assert ss._survivor_factor(67, 60) == pytest.approx(0.715)
    # Linear interpolation between 60 and FRA.
    assert ss._survivor_factor(66, 63) == pytest.approx(1.0 - 0.285 * 3 / 6)
    assert ss._survivor_factor(67, 63.5) == pytest.approx(1.0 - 0.285 * 3.5 / 7)


def test_compute_ss_survivor_age_reduction():
    """Survivor below survivor FRA: benefit reduced by survivor claiming-age factor."""
    thisyear = 2026  # fixed for a deterministic calculation
    yobs = np.array([1958, 1966])  # person 0 age 68, person 1 age 60
    pias = np.array([2000, 400])
    ages = np.array([68.0, 62.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 15])
    horizons = np.array([2, 20])  # person 0 dies at year 2
    N_i, N_n = 2, 20

    zeta_in, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, thisyear=thisyear
    )

    # Deceased (person 0): retirement FRA = 66+8/12, claims at 68 (with DRC).
    fra_0 = ss.getFRAs(yobs[:1], mobs[:1], tobs[:1])[0]
    deceased_monthly = pias[0] * ss.getSelfFactor(fra_0, 68.0, False)
    # Floor check: deceased's actual > 82.5%×PIA, so no floor needed here.
    assert deceased_monthly > 0.825 * pias[0]

    # Survivor (person 1): age 62 at death_year_n=2, survivor FRA=67.
    survivor_fra = ss.getSurvivorFRAs(yobs[1:2], mobs[1:2], tobs[1:2])[0]  # 67
    survivor_age = (thisyear + 2) - yobs[1]  # 62
    factor = ss._survivor_factor(survivor_fra, survivor_age)
    expected_annual = deceased_monthly * factor * 12

    # Year 3 is a clean full-benefit year (no partial-payment edge effects).
    assert zeta_in[1, 3] == pytest.approx(expected_annual, rel=0.01)


def test_getSpousalBenefits_raises():
    """getSpousalBenefits raises ValueError for arrays with more than 2 entries."""
    with pytest.raises(ValueError):
        ss.getSpousalBenefits([1000, 2000, 3000])


def test_getSelfFactor_raises():
    """getSelfFactor raises ValueError for age outside [62, 70]."""
    with pytest.raises(ValueError):
        ss.getSelfFactor(66, 61.9, False)
    with pytest.raises(ValueError):
        ss.getSelfFactor(66, 70.1, False)


def test_getSpousalFactor_raises():
    """getSpousalFactor raises ValueError for age below 62."""
    with pytest.raises(ValueError):
        ss.getSpousalFactor(66, 61.9, False)


def test_compute_ss_survivor():
    """Couple with different horizons: survivor receives the higher-earning spouse's benefit."""
    from datetime import date

    thisyear = date.today().year
    # Person 0 dies at year 10, person 1 lives to year 20.
    yobs = np.array([thisyear - 70, thisyear - 67])
    pias = np.array([2000, 1000])
    ages = np.array([70.0, 67.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 15])
    horizons = np.array([10, 20])
    N_i, N_n = 2, 20

    zeta_in, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert zeta_in.shape == (2, 20)
    # Person 0 has no benefits on or after their horizon.
    assert np.all(zeta_in[0, 10:] == 0)
    # Survivor (person 1) receives person 0's annual benefit from year 10 onward.
    assert zeta_in[1, 10] == pytest.approx(zeta_in[0, 9])
    assert zeta_in[1, 19] == pytest.approx(zeta_in[0, 9])


def test_compute_ss_spousal_benefit():
    """Lower-earning spouse receives a spousal benefit on top of their own benefit."""
    from datetime import date

    thisyear = date.today().year
    yob = thisyear - 67
    yobs = np.array([yob, yob])
    pias = np.array([2000, 500])  # person 1 qualifies: 0.5*2000 - 500 = 500 > 0
    ages = np.array([67.0, 67.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 15])
    horizons = np.array([20, 20])
    N_i, N_n = 2, 20

    zeta_in, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, thisyear=thisyear
    )
    assert zeta_in.shape == (2, 20)
    fras = ss.getFRAs(yobs, mobs, tobs)
    own_factor = ss.getSelfFactor(fras[1], 67.0, False)
    spousal_factor = ss.getSpousalFactor(fras[1], 67.0, False)
    # Year 5 is a full year (no partial-payment edge effects).
    expected_annual = (500 * own_factor + 500 * spousal_factor) * 12
    assert zeta_in[1, 5] == pytest.approx(expected_annual, rel=0.01)


def test_compute_ss_born_on_2nd():
    """Born-on-2nd: eligible at conventional 62 (same as born-on-1st) but factor has no +1/12 shift."""
    from datetime import date

    thisyear = date.today().year
    yob = 1954  # FRA = 66 exactly; claiming in the past is fine for a steady-state check
    pias = np.array([2000])
    yobs = np.array([yob])
    mobs = np.array([6])  # born June
    horizons = np.array([30])
    N_i, N_n = 1, 30

    # Born mid-month: minimum eligible age is 62 + 1/12.
    _, ages_mid = ss.compute_social_security_benefits(
        pias, np.array([60.0]), yobs, mobs, np.array([15]), horizons, N_i, N_n, thisyear=thisyear
    )
    assert ages_mid[0] == pytest.approx(62 + 1 / 12)

    # Born on 2nd: minimum eligible age is 62 (same as born on 1st), no factor shift.
    zeta_2nd, ages_2nd = ss.compute_social_security_benefits(
        pias, np.array([60.0]), yobs, mobs, np.array([2]), horizons, N_i, N_n, thisyear=thisyear
    )
    assert ages_2nd[0] == pytest.approx(62.0)

    # Factor for born-on-2nd at FRA=66, claiming age=62: no +1/12 shift → 0.75, not ~0.754.
    fra = ss.getFRAs(yobs, mobs, np.array([2]))[0]  # 66 (born June 2nd)
    expected_annual = 2000 * ss.getSelfFactor(fra, 62, False) * 12  # bornOnFirst=False
    assert expected_annual == pytest.approx(2000 * 0.75 * 12)
    assert zeta_2nd[0, 5] == pytest.approx(expected_annual, rel=0.01)


def test_compute_ss_survivor_pia_floor():
    """Survivor receives max(deceased actual, 82.5%×PIA) when deceased claimed early."""
    from datetime import date

    thisyear = date.today().year
    # Person 0 (born 1960+, FRA=67) claims at 62 → factor 0.70, below the 82.5% floor.
    yobs = np.array([thisyear - 62, thisyear - 67])
    pias = np.array([2000, 400])  # person 1's own benefit is well below the floor
    ages = np.array([62.0, 67.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 15])
    horizons = np.array([5, 20])  # person 0 dies at year 5, person 1 lives to year 20
    N_i, N_n = 2, 20

    zeta_in, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, thisyear=thisyear
    )
    # Deceased actual (0.70 × 2000 = 1400/month) < floor (0.825 × 2000 = 1650/month).
    # Survivor (person 1) should receive the floor amount from year 5 onward.
    expected_annual = 0.825 * pias[0] * 12  # = 19800
    assert zeta_in[1, 5] == pytest.approx(expected_annual, rel=0.01)
    assert zeta_in[1, 15] == pytest.approx(expected_annual, rel=0.01)


def test_survivor_min_age_60():
    """Survivor under 60 at death: factor clamped to age-60 floor (71.5%)."""
    # Age 55 is below SSA minimum; factor must equal the age-60 value (0.715).
    assert ss._survivor_factor(67, 55) == pytest.approx(ss._survivor_factor(67, 60))
    assert ss._survivor_factor(67, 55) == pytest.approx(0.715)
    # Age 59 is also below minimum; same result.
    assert ss._survivor_factor(67, 59) == pytest.approx(0.715)
    # Confirm floor holds for a different survivor FRA schedule.
    assert ss._survivor_factor(66, 55) == pytest.approx(0.715)
    # Age 60 itself returns exactly 0.715 (unchanged by either FRA schedule).
    assert ss._survivor_factor(66, 60) == pytest.approx(0.715)
    assert ss._survivor_factor(67, 60) == pytest.approx(0.715)


def test_compute_ss_trim():
    """Trim reduces benefits from trim_year onward by trim_pct percent."""
    from datetime import date

    thisyear = date.today().year
    yob = thisyear - 67
    pias = np.array([2000])
    ages = np.array([67.0])
    yobs = np.array([yob])
    mobs = np.array([1])
    tobs = np.array([15])
    horizons = np.array([20])
    N_i, N_n = 1, 20

    zeta_base, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, thisyear=thisyear
    )
    zeta_trim, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, trim_pct=20, trim_year=thisyear + 10, thisyear=thisyear
    )
    # Benefits before the trim year are unchanged.
    assert np.allclose(zeta_trim[0, :10], zeta_base[0, :10])
    # Benefits from trim_year onward are reduced by 20%.
    assert np.allclose(zeta_trim[0, 10:], zeta_base[0, 10:] * 0.8)


# ---------------------------------------------------------------------------
# Survivor claiming age
# ---------------------------------------------------------------------------

# A widow(er) whose own benefit is the larger one but has not started it yet when
# their spouse dies.  Deceased PIA 2000 claimed at 67; survivor PIA 3000 claiming at 70;
# first death when the survivor is 68, i.e. already past their survivor FRA of 67.
_LATE_OWN_CLAIM = dict(
    pias=[2000, 3000],
    ages=[67.0, 70.0],
    mobs=np.array([6, 6]),
    tobs=np.array([15, 15]),
    horizons=np.array([5, 30]),
    N_i=2,
    N_n=30,
)


def _late_own_claim(thisyear, survivor_claim_age="immediate"):
    kwargs = dict(_LATE_OWN_CLAIM)
    yobs = np.array([thisyear - 68, thisyear - 63])
    zeta_in, _ = ss.compute_social_security_benefits(
        kwargs.pop("pias"),
        kwargs.pop("ages"),
        yobs,
        kwargs.pop("mobs"),
        kwargs.pop("tobs"),
        kwargs.pop("horizons"),
        kwargs.pop("N_i"),
        kwargs.pop("N_n"),
        thisyear=thisyear,
        survivor_claim_age=survivor_claim_age,
    )
    return zeta_in


def test_survivor_keeps_own_benefit():
    """Survivor who has not yet claimed does not forfeit their own (larger) benefit.

    Regression: the survivor benefit used to overwrite the survivor's whole remaining
    horizon, erasing an own benefit that had not started by the year of the first death.
    """
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([thisyear - 68, thisyear - 63])
    mobs, tobs = np.array([6, 6]), np.array([15, 15])
    fras = ss.getFRAs(yobs, mobs, tobs)
    zeta_in = _late_own_claim(thisyear)

    # Years 5-7: survivor is 68-70 and collects the deceased's benefit.
    deceased_annual = 2000 * ss.getSelfFactor(fras[0], 67.0, False) * 12
    assert zeta_in[1, 5] == pytest.approx(deceased_annual)
    assert zeta_in[1, 7] == pytest.approx(deceased_annual)
    # From year 8 the survivor's own age-70 benefit is larger and takes over.
    own_at_70 = 3000 * ss.getSelfFactor(fras[1], 70.0, False) * 12
    assert zeta_in[1, 8] == pytest.approx(own_at_70)
    assert zeta_in[1, 29] == pytest.approx(own_at_70)
    assert own_at_70 > deceased_annual


def test_survivor_receives_greater_of_two_benefits():
    """A survivor whose own benefit already exceeds the survivor benefit keeps their own."""
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([thisyear - 70, thisyear - 68])
    pias = np.array([1000, 3000])  # deceased is the *lower* earner
    ages = np.array([67.0, 67.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 15])
    horizons = np.array([5, 20])

    zeta_in, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, 2, 20, thisyear=thisyear
    )
    own_annual = 3000 * ss.getSelfFactor(ss.getFRAs(yobs, mobs, tobs)[1], 67.0, False) * 12
    # Survivor's own benefit is unchanged by the first death.
    assert zeta_in[1, 10] == pytest.approx(zeta_in[1, 4])
    assert zeta_in[1, 10] == pytest.approx(own_annual)


def test_survivor_spousal_addon_ends_at_first_death():
    """The spousal add-on stops at the first death; only the survivor benefit continues."""
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([thisyear - 65, thisyear - 72])
    pias = np.array([3000, 1200])  # person 1 gets a 0.5*3000 - 1200 = 300/month add-on
    ages = np.array([67.0, 62.0])
    mobs = np.array([6, 6])
    tobs = np.array([15, 15])
    horizons = np.array([7, 26])

    assert ss.getSpousalBenefits(pias)[1] == pytest.approx(300)
    zeta_in, adj_ages = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, 2, 26, thisyear=thisyear
    )
    fras = ss.getFRAs(yobs, mobs, tobs)
    # Before the death the survivor collects own + spousal add-on (both past their FRAs).
    own_1 = 1200 * ss.getSelfFactor(fras[1], adj_ages[1], False) * 12
    assert zeta_in[1, 6] == pytest.approx(own_1 + 300 * 12)
    # After the death: the deceased's full benefit, with no spousal amount stacked on top.
    deceased_annual = 3000 * ss.getSelfFactor(fras[0], 67.0, False) * 12
    assert zeta_in[1, 10] == pytest.approx(deceased_annual)


# Survivor well below their survivor FRA (67) at the first death: the three settings differ.
def _early_widow(thisyear, survivor_claim_age):
    yobs = np.array([thisyear - 71, thisyear - 56])
    zeta_in, _ = ss.compute_social_security_benefits(
        np.array([3000, 1500]),
        np.array([67.0, 67.0]),
        yobs,
        np.array([6, 6]),
        np.array([15, 15]),
        np.array([5, 40]),  # first death in year 5, when the survivor is 60.6
        2,
        40,
        thisyear=thisyear,
        survivor_claim_age=survivor_claim_age,
    )
    return zeta_in


def test_survivor_claim_age_immediate_is_reduced():
    """Claiming immediately below survivor FRA locks in a permanent reduction."""
    from datetime import date

    thisyear = date.today().year
    zeta_in = _early_widow(thisyear, "immediate")
    deceased_monthly = 3000 * ss.getSelfFactor(66 + 2 / 12, 67.0, False)
    factor = ss._survivor_factor(67, 61 - 5 / 12)
    assert factor < 1.0
    assert zeta_in[1, 5] == pytest.approx(deceased_monthly * factor * 12)
    assert zeta_in[1, 20] == pytest.approx(deceased_monthly * factor * 12)


def test_survivor_claim_age_fra_is_unreduced():
    """Deferring to the survivor FRA pays the full amount, with nothing in between."""
    from datetime import date

    thisyear = date.today().year
    zeta_in = _early_widow(thisyear, "FRA")
    deceased_monthly = 3000 * ss.getSelfFactor(66 + 2 / 12, 67.0, False)
    # Nothing between the first death (survivor age 60.6) and the survivor's own claim at 67.
    assert np.all(zeta_in[1, 5:11] == 0)
    # Year 11 is the survivor's 67th year: half a year of survivor benefit (born mid-year).
    assert zeta_in[1, 11] == pytest.approx(deceased_monthly * 12 * 0.5)
    # Full unreduced survivor benefit thereafter, above their own 1500/month.
    assert zeta_in[1, 12] == pytest.approx(deceased_monthly * 12)
    assert zeta_in[1, 12] > 1500 * 12


def test_survivor_claim_age_explicit():
    """An explicit claiming age sits between the immediate and FRA outcomes."""
    from datetime import date

    thisyear = date.today().year
    z_now = _early_widow(thisyear, "immediate")
    z_64 = _early_widow(thisyear, 64)
    z_fra = _early_widow(thisyear, "FRA")
    # Steady-state amounts are ordered by claiming age.
    assert z_now[1, 20] < z_64[1, 20] < z_fra[1, 20]
    # Claiming at 64 pays nothing until then, unlike claiming immediately.
    assert z_64[1, 5] == 0
    assert z_now[1, 5] > 0


def test_survivor_claim_age_capped_at_survivor_fra():
    """Survivor benefits earn no delayed credits, so an age past survivor FRA is capped."""
    from datetime import date

    thisyear = date.today().year
    assert np.allclose(_early_widow(thisyear, 70), _early_widow(thisyear, "FRA"))


def test_survivor_cannot_claim_before_60():
    """A survivor under 60 at the first death collects nothing until age 60."""
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([thisyear - 71, thisyear - 50])
    zeta_in, _ = ss.compute_social_security_benefits(
        np.array([3000, 1500]),
        np.array([67.0, 67.0]),
        yobs,
        np.array([6, 6]),
        np.array([15, 15]),
        np.array([5, 40]),  # first death in year 5, when the survivor is only 54.6
        2,
        40,
        thisyear=thisyear,
        survivor_claim_age="immediate",
    )
    # Survivor turns 60 in year 10; nothing is paid before then.
    assert np.all(zeta_in[1, 5:10] == 0)
    assert zeta_in[1, 11] > 0
    # And the amount carries the age-60 minimum factor of 71.5%.
    deceased_monthly = 3000 * ss.getSelfFactor(66 + 2 / 12, 67.0, False)
    assert zeta_in[1, 11] == pytest.approx(deceased_monthly * 0.715 * 12)


def test_validate_survivor_claim_age():
    """Keyword and numeric forms are normalized; anything else is rejected."""
    assert ss.validate_survivor_claim_age("immediate") == "immediate"
    assert ss.validate_survivor_claim_age("fra") == "FRA"
    assert ss.validate_survivor_claim_age(65) == 65.0
    assert ss.validate_survivor_claim_age("62.5") == 62.5
    for bad in ("nonsense", 59, 71):
        with pytest.raises(ValueError):
            ss.validate_survivor_claim_age(bad)


def test_compute_survivor_stream_no_survivor_period():
    """Single individuals and equal horizons produce an empty survivor stream."""
    from datetime import date

    thisyear = date.today().year
    survivor = ss.compute_survivor_stream(
        np.array([2000]), np.array([67.0]), np.array([thisyear - 67]), _M, _T, np.array([20]), 1, 20,
        thisyear=thisyear,
    )
    assert survivor.survivor_idx == -1
    assert np.all(survivor.annual == 0)


def test_apply_survivor_to_benefit_table():
    """Folding the survivor stream into the own-benefit table takes the greater of the two."""
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([thisyear - 68, thisyear - 63])
    pias = np.array([2000, 3000])
    ages = np.array([67.0, 70.0])
    mobs = np.array([6, 6])
    tobs = np.array([15, 15])
    horizons = np.array([5, 30])
    N_n = 30
    gamma_n = np.ones(N_n)

    fras = ss.getFRAs(yobs, mobs, tobs)
    B_own, ages_k = ss.build_own_benefit_table(
        pias, fras, yobs, mobs, tobs, horizons, 2, N_n, gamma_n, thisyear=thisyear
    )
    survivor = ss.compute_survivor_stream(
        pias, ages, yobs, mobs, tobs, horizons, 2, N_n, thisyear=thisyear
    )
    B_eff = ss.apply_survivor_to_benefit_table(B_own, survivor, gamma_n)

    nd = survivor.death_year_n
    # The deceased's rows and all pre-death years are untouched.
    assert np.allclose(B_eff[0], B_own[0])
    assert np.allclose(B_eff[1, :, :nd], B_own[1, :, :nd])
    # Post-death entries are the greater of own benefit and survivor benefit, for every k.
    assert np.allclose(B_eff[1, :, nd:], np.maximum(B_own[1, :, nd:], survivor.annual[nd:]))
    # The table matches the combined series for the claiming age actually in force.
    k = int(round((ages[1] - 62.0) * 12))
    zeta_in, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, 2, N_n, thisyear=thisyear
    )
    assert ages_k[k] == pytest.approx(ages[1])
    assert np.allclose(B_eff[1, k, nd:], zeta_in[1, nd:])


# ---------------------------------------------------------------------------
# Pathological / boundary cases for the survivor stream
# ---------------------------------------------------------------------------


def _survivor_case(thisyear, survivor_claim_age, *, surv_age_now, horizons, N_n, pias=(3000, 1500)):
    """Couple where person 0 dies first; person 1 is `surv_age_now` today."""
    yobs = np.array([thisyear - 71, thisyear - surv_age_now])
    return ss.compute_survivor_stream(
        np.array(pias),
        np.array([67.0, 67.0]),
        yobs,
        np.array([6, 6]),
        np.array([15, 15]),
        np.array(horizons),
        2,
        N_n,
        survivor_claim_age=survivor_claim_age,
        thisyear=thisyear,
    )


def test_survivor_cannot_claim_before_the_first_death():
    """An age already passed at the first death resolves to the death year, not earlier."""
    from datetime import date

    thisyear = date.today().year
    # Survivor is 68 today, so ~72.6 (born mid-year) at the first death in plan year 5.
    age_at_death = (thisyear + 5) - (thisyear - 68) - 5 / 12
    for setting in ("immediate", "FRA", 62, 65, 67):
        surv = _survivor_case(thisyear, setting, surv_age_now=68, horizons=[5, 25], N_n=25)
        assert surv.claim_age >= age_at_death - 1e-9, (
            f"{setting}: claim age {surv.claim_age} precedes the death at {age_at_death}"
        )
        assert np.all(surv.annual[: surv.death_year_n] == 0), f"{setting}: benefit paid before the death"
        assert surv.annual[surv.death_year_n] > 0


def test_survivor_claim_age_never_below_60_or_above_survivor_fra():
    """The resolved claiming age stays inside [60, survivor FRA] for any requested value."""
    from datetime import date

    thisyear = date.today().year
    for setting in ("immediate", "FRA", 60, 63, 70):
        # Survivor is 50 today, 55 at the first death: well under the age-60 minimum.
        surv = _survivor_case(thisyear, setting, surv_age_now=50, horizons=[5, 40], N_n=40)
        assert 60 <= surv.claim_age <= surv.survivor_fra + 1e-9


def test_survivor_stream_empty_when_death_is_past_the_horizon():
    """A first death at or beyond the plan horizon produces no survivor stream."""
    from datetime import date

    thisyear = date.today().year
    surv = _survivor_case(thisyear, "immediate", surv_age_now=68, horizons=[20, 20], N_n=20)
    assert surv.survivor_idx == -1
    assert np.all(surv.annual == 0)


def test_survivor_stream_fits_within_the_plan_horizon():
    """A claiming date past the end of a short plan yields no payments, not an error."""
    from datetime import date

    thisyear = date.today().year
    # Survivor is 40 today: their survivor FRA falls well outside this 6-year plan.
    surv = _survivor_case(thisyear, "FRA", surv_age_now=40, horizons=[3, 6], N_n=6)
    assert surv.annual.shape == (6,)
    assert np.all(surv.annual == 0)


def test_survivor_with_death_in_first_plan_year():
    """A first death in year 0 is handled without touching negative indices."""
    from datetime import date

    thisyear = date.today().year
    zeta_in, _ = ss.compute_social_security_benefits(
        np.array([3000, 1500]),
        np.array([67.0, 67.0]),
        np.array([thisyear - 71, thisyear - 70]),
        np.array([6, 6]),
        np.array([15, 15]),
        np.array([0, 20]),
        2,
        20,
        thisyear=thisyear,
    )
    assert np.all(zeta_in[0] == 0)
    assert zeta_in[1, 0] > 0  # survivor benefit starts immediately


def test_survivor_with_zero_pia_deceased():
    """A deceased spouse with no earnings record leaves the survivor on their own benefit."""
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([thisyear - 71, thisyear - 70])
    zeta_in, _ = ss.compute_social_security_benefits(
        np.array([0, 1500]),
        np.array([67.0, 67.0]),
        yobs,
        np.array([6, 6]),
        np.array([15, 15]),
        np.array([5, 20]),
        2,
        20,
        thisyear=thisyear,
    )
    own = 1500 * ss.getSelfFactor(ss.getFRAs(yobs, [6], [15])[1], 67.0, False) * 12
    assert zeta_in[1, 10] == pytest.approx(own)


def test_survivor_claim_age_ignored_for_single_individual():
    """The setting is inert for a single individual rather than an error."""
    from datetime import date

    thisyear = date.today().year
    base, _ = ss.compute_social_security_benefits(
        np.array([2000]), np.array([67.0]), np.array([thisyear - 67]), _M, _T, np.array([20]), 1, 20,
        thisyear=thisyear,
    )
    for setting in ("immediate", "FRA", 63):
        other, _ = ss.compute_social_security_benefits(
            np.array([2000]), np.array([67.0]), np.array([thisyear - 67]), _M, _T, np.array([20]), 1, 20,
            thisyear=thisyear, survivor_claim_age=setting,
        )
        assert np.allclose(base, other)


# ---------------------------------------------------------------------------
# survivor_claim_window: the payable range, derived from dates alone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "yob_a,life_a,yob_b,life_b",
    [
        (1963, 89, 1966, 92),  # older spouse dies first, survivor well past survivor FRA
        (1963, 64, 1966, 95),  # early death, survivor below their survivor FRA
        (1966, 95, 1963, 64),  # same, with the individuals swapped
        (1955, 80, 1970, 95),  # wide age gap
        (1960, 70, 1960, 95),  # 1960 cohort: survivor FRA differs from retirement FRA
    ],
)
def test_survivor_claim_window_matches_the_computed_stream(yob_a, life_a, yob_b, life_b):
    """The window derived from dates alone must agree with compute_survivor_stream.

    The UI uses this to bound the claiming-age input before a plan exists, so the two
    must not drift apart.
    """
    from datetime import date

    thisyear = date.today().year
    yobs = np.array([yob_a, yob_b])
    mobs, tobs = np.array([6, 6]), np.array([15, 15])
    ends = [yob_a + life_a, yob_b + life_b]
    horizons = np.array([ends[i] + 1 - thisyear for i in range(2)])
    N_n = int(max(horizons))

    window = ss.survivor_claim_window(yobs, mobs, tobs, ends)
    surv = ss.compute_survivor_stream(
        np.array([3000, 2000]), np.array([67.0, 67.0]), yobs, mobs, tobs, horizons, 2, N_n,
        thisyear=thisyear,
    )
    assert window is not None
    assert window["survivor_idx"] == surv.survivor_idx
    assert window["deceased_idx"] == surv.deceased_idx
    assert window["survivor_fra"] == pytest.approx(surv.survivor_fra)
    assert window["age_at_first_passing"] == pytest.approx(surv.age_at_death)


def test_survivor_claim_window_none_without_a_survivor_period():
    """Lifespans ending in the same year leave no survivor period."""
    # 1963 + 89 == 1966 + 86 == 2052.
    assert ss.survivor_claim_window([1963, 1966], [6, 6], [15, 15], [2052, 2052]) is None
    assert ss.survivor_claim_window([1963], [6], [15], [2052]) is None


def test_survivor_claim_window_upper_bound_is_the_survivor_fra():
    """The window's upper end is the survivor FRA, which can precede the retirement FRA."""
    window = ss.survivor_claim_window([1955, 1960], [6, 6], [15, 15], [2035, 2060])
    assert window["survivor_idx"] == 1
    assert window["survivor_fra"] == pytest.approx(66 + 8 / 12)  # not 67
    assert ss.getFRAs([1960], [6], [15])[0] == pytest.approx(67.0)
