"""
Tests for the SSA 2025 period life table mortality module.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import numpy as np
import pytest

from owlplanner.data.mortality_tables import survival_pmf, sample_lifespans, life_expectancy


class TestSurvivalPmf:
    def test_pmf_sums_to_one(self):
        for sex in ("M", "F"):
            _, pmf = survival_pmf(sex, 65)
            assert abs(pmf.sum() - 1.0) < 1e-9

    def test_ages_start_at_current_age(self):
        ages, _ = survival_pmf("M", 70)
        assert ages[0] == 70

    def test_ages_end_at_119(self):
        ages, _ = survival_pmf("F", 50)
        assert ages[-1] == 119

    def test_all_pmf_values_positive(self):
        _, pmf = survival_pmf("M", 65)
        assert np.all(pmf > 0)

    def test_invalid_sex_raises(self):
        with pytest.raises(ValueError, match="sex"):
            survival_pmf("X", 65)

    def test_age_out_of_range_raises(self):
        with pytest.raises(ValueError, match="current_age"):
            survival_pmf("M", 120)

    def test_female_lives_longer_than_male(self):
        le_m = life_expectancy("M", 65)
        le_f = life_expectancy("F", 65)
        assert le_f > le_m

    def test_life_expectancy_increases_with_age(self):
        """Conditional life expectancy at older ages should be higher (survival bias)."""
        le_65 = life_expectancy("M", 65)
        le_75 = life_expectancy("M", 75)
        assert le_75 > le_65

    def test_life_expectancy_at_birth_male(self):
        """Male life expectancy at birth should be approximately 74 years (SSA 2025: 74.74)."""
        le = life_expectancy("M", 0)
        assert 73.0 < le < 76.0

    def test_life_expectancy_at_birth_female(self):
        """Female life expectancy at birth should be approximately 80 years (SSA 2025: 80.18)."""
        le = life_expectancy("F", 0)
        assert 78.0 < le < 82.0


class TestSampleLifespans:
    def test_returns_correct_shape(self):
        samples = sample_lifespans("M", 65, 100)
        assert samples.shape == (100,)

    def test_samples_within_valid_range(self):
        samples = sample_lifespans("F", 70, 1000, rng=np.random.default_rng(0))
        assert np.all(samples >= 70)
        assert np.all(samples <= 119)

    def test_sample_mean_near_life_expectancy(self):
        le = life_expectancy("M", 65)
        samples = sample_lifespans("M", 65, 10000, rng=np.random.default_rng(42))
        assert abs(samples.mean() - le) < 0.5

    def test_reproducible_with_seed(self):
        s1 = sample_lifespans("F", 60, 50, rng=np.random.default_rng(7))
        s2 = sample_lifespans("F", 60, 50, rng=np.random.default_rng(7))
        np.testing.assert_array_equal(s1, s2)

    def test_default_rng_does_not_raise(self):
        samples = sample_lifespans("M", 65, 10)
        assert len(samples) == 10
