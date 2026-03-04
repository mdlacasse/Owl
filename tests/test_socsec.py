"""
Tests for socialsecurity module - Social Security benefit calculations.

Tests verify Social Security rules including full retirement age calculations
and benefit computations.

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
        assert yfra[0] % 1 == pytest.approx(2*i/12)

    yfra = ss.getFRAs([1940], _M, _T)
    assert yfra[0] == pytest.approx(65.5)
    yfra = ss.getFRAs([1938], _M, _T)
    assert yfra[0] == pytest.approx(65 + 2/12)
    yfra = ss.getFRAs([1942], _M, _T)
    assert yfra[0] == pytest.approx(65 + 10/12)
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
    assert yfra[0] == pytest.approx(66 + 10/12)
    yfra = ss.getFRAs([1960], [6], [15])
    assert yfra[0] == 67
    yfra = ss.getSurvivorFRAs([1962], [1], [1])
    assert yfra[0] == pytest.approx(66 + 10/12)
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
            assert ss.getSelfFactor(66, a - 1/12, True) == pytest.approx(factors66[i], 0.001)
            assert ss.getSelfFactor(67, a - 1/12, True) == pytest.approx(factors67[i], 0.001)

    # Example from SSA: https://www.ssa.gov/benefits/retirement/planner/1955-delay.html
    assert ss.getSelfFactor(66 + 2/12, 66 + 2/12, False) == pytest.approx(1.00, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 67, False) == pytest.approx(1.06667, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 68, False) == pytest.approx(1.14667, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 69, False) == pytest.approx(1.22667, 0.001)
    assert ss.getSelfFactor(66 + 3/12, 69 + 1/12, False) == pytest.approx(1.22667, 0.001)
    assert ss.getSelfFactor(66 + 2/12, 70, False) == pytest.approx(1.30667, 0.001)


def test_spousalFactor():
    ages = range(62, 71)
    factors66 = [0.70, 0.75, 0.833333, 0.9166667, 1.0, 1.0, 1.0, 1.0, 1.0]
    factors67 = [0.65, 0.70, 0.75, 0.833333, 0.9166667, 1.0, 1.0, 1.0, 1.0]
    for i, a in enumerate(ages):
        assert ss.getSpousalFactor(66, a, False) == pytest.approx(factors66[i], 0.001)
        assert ss.getSpousalFactor(67, a, False) == pytest.approx(factors67[i], 0.001)
        if a > 62:
            assert ss.getSpousalFactor(66, a - 1/12, True) == pytest.approx(factors66[i], 0.001)
            assert ss.getSpousalFactor(67, a - 1/12, True) == pytest.approx(factors67[i], 0.001)

    # Individual born in 1955.
    assert ss.getSpousalFactor(66 + 2/12, 66 + 2/12, False) == pytest.approx(1.00, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 66, False) == pytest.approx(2*0.4931, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 65, False) == pytest.approx(2*0.4514, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 64, False) == pytest.approx(2*0.4097, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 63, False) == pytest.approx(2*0.3708, 0.001)
    assert ss.getSpousalFactor(66 + 2/12, 62, False) == pytest.approx(2*0.3458, 0.001)


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

    zeta_in, ages_out = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n
    )
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

    zeta_in, ages_out = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n
    )
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

    zeta_in, ages_out = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n
    )
    assert ages_out[0] == pytest.approx(62.0)
    assert ages[0] == pytest.approx(60.0)  # Original unchanged (we copy)


def test_survivor_FRA():
    """Verify survivor FRA schedule matches SSA table (distinct from retirement FRA)."""
    assert ss.getSurvivorFRAs([1939], _M, _T)[0] == pytest.approx(65)
    assert ss.getSurvivorFRAs([1900], _M, _T)[0] == pytest.approx(65)
    assert ss.getSurvivorFRAs([1940], _M, _T)[0] == pytest.approx(65 + 2/12)
    assert ss.getSurvivorFRAs([1944], _M, _T)[0] == pytest.approx(65 + 10/12)
    assert ss.getSurvivorFRAs([1945], _M, _T)[0] == pytest.approx(66)
    assert ss.getSurvivorFRAs([1956], _M, _T)[0] == pytest.approx(66)
    assert ss.getSurvivorFRAs([1957], _M, _T)[0] == pytest.approx(66 + 2/12)
    assert ss.getSurvivorFRAs([1961], _M, _T)[0] == pytest.approx(66 + 10/12)
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
    yobs = np.array([1958, 1966])   # person 0 age 68, person 1 age 60
    pias = np.array([2000, 400])
    ages = np.array([68.0, 62.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 15])
    horizons = np.array([2, 20])    # person 0 dies at year 2
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
    survivor_fra = ss.getSurvivorFRAs(yobs[1:2], mobs[1:2], tobs[1:2])[0]   # 67
    survivor_age = (thisyear + 2) - yobs[1]            # 62
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
    mobs = np.array([6])   # born June
    horizons = np.array([30])
    N_i, N_n = 1, 30

    # Born mid-month: minimum eligible age is 62 + 1/12.
    _, ages_mid = ss.compute_social_security_benefits(
        pias, np.array([60.0]), yobs, mobs, np.array([15]), horizons, N_i, N_n, thisyear=thisyear
    )
    assert ages_mid[0] == pytest.approx(62 + 1/12)

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
    pias = np.array([2000, 400])   # person 1's own benefit is well below the floor
    ages = np.array([62.0, 67.0])
    mobs = np.array([1, 1])
    tobs = np.array([15, 15])
    horizons = np.array([5, 20])   # person 0 dies at year 5, person 1 lives to year 20
    N_i, N_n = 2, 20

    zeta_in, _ = ss.compute_social_security_benefits(
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n, thisyear=thisyear
    )
    # Deceased actual (0.70 × 2000 = 1400/month) < floor (0.825 × 2000 = 1650/month).
    # Survivor (person 1) should receive the floor amount from year 5 onward.
    expected_annual = 0.825 * pias[0] * 12   # = 19800
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
        pias, ages, yobs, mobs, tobs, horizons, N_i, N_n,
        trim_pct=20, trim_year=thisyear + 10, thisyear=thisyear
    )
    # Benefits before the trim year are unchanged.
    assert np.allclose(zeta_trim[0, :10], zeta_base[0, :10])
    # Benefits from trim_year onward are reduced by 20%.
    assert np.allclose(zeta_trim[0, 10:], zeta_base[0, 10:] * 0.8)
