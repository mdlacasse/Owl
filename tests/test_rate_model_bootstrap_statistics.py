import numpy as np
import pandas as pd

from owlplanner.rate_models.bootstrap_sor import BootstrapSORRateModel


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_historical_slice(frm, to):
    import os
    import sys

    where = os.path.dirname(sys.modules["owlplanner"].__file__)
    file = os.path.join(where, "data/rates.csv")
    df = pd.read_csv(file)

    df = df[(df["year"] >= frm) & (df["year"] <= to)]

    data = df[["S&P 500", "Bonds Baa", "T-Notes", "Inflation"]].values / 100.0
    return data


def compute_stats(data):
    return {
        "mean": np.mean(data, axis=0),
        "std": np.std(data, axis=0),
        "corr": np.corrcoef(data.T),
    }


def compute_autocorr(data):
    # 1-lag autocorrelation for each column
    ac = []
    for k in range(data.shape[1]):
        x = data[:, k]
        ac.append(np.corrcoef(x[:-1], x[1:])[0, 1])
    return np.array(ac)


# ---------------------------------------------------------
# Core Distribution Fidelity Test
# ---------------------------------------------------------

def test_bootstrap_distribution_matches_historical():
    frm, to = 1950, 2020
    N = 30
    sims = 2000  # Monte Carlo replications

    hist = get_historical_slice(frm, to)
    hist_stats = compute_stats(hist)

    model = BootstrapSORRateModel(
        config={"frm": frm, "to": to},
        seed=1234,
    )

    samples = []

    for _ in range(sims):
        series = model.generate(N)
        samples.append(series)

    samples = np.vstack(samples)

    boot_stats = compute_stats(samples)

    # -----------------------------
    # Mean should be close
    # -----------------------------
    assert np.allclose(
        boot_stats["mean"],
        hist_stats["mean"],
        atol=0.01
    )

    # -----------------------------
    # Std deviation should be close
    # -----------------------------
    assert np.allclose(
        boot_stats["std"],
        hist_stats["std"],
        atol=0.01
    )

    # -----------------------------
    # Correlation matrix similar
    # -----------------------------
    assert np.allclose(
        boot_stats["corr"],
        hist_stats["corr"],
        atol=0.05
    )


# ---------------------------------------------------------
# Autocorrelation Tests
# ---------------------------------------------------------

def test_iid_bootstrap_has_near_zero_autocorr():
    frm, to = 1950, 2020
    N = 5000

    model = BootstrapSORRateModel(
        config={
            "frm": frm,
            "to": to,
            "bootstrap_type": "iid"
        },
        seed=42,
    )

    series = model.generate(N)
    ac = compute_autocorr(series)

    # IID should have very low autocorrelation
    assert np.all(np.abs(ac) < 0.05)


def test_block_bootstrap_preserves_positive_autocorr():
    frm, to = 1950, 2020
    N = 5000

    model = BootstrapSORRateModel(
        config={
            "frm": frm,
            "to": to,
            "bootstrap_type": "block",
            "block_size": 5,
        },
        seed=42,
    )

    series = model.generate(N)
    ac = compute_autocorr(series)

    # Block bootstrap should show some persistence
    assert np.any(ac > 0.05)


# ---------------------------------------------------------
# Crisis Overweight Test
# ---------------------------------------------------------

def test_crisis_overweight_increases_crisis_frequency():
    frm, to = 1950, 2020
    N = 10000
    crisis_years = [1974, 2008]

    base_model = BootstrapSORRateModel(
        config={"frm": frm, "to": to},
        seed=123,
    )

    crisis_model = BootstrapSORRateModel(
        config={
            "frm": frm,
            "to": to,
            "crisis_years": crisis_years,
            "crisis_weight": 5.0,
        },
        seed=123,
    )

    base_series = base_model.generate(N)
    crisis_series = crisis_model.generate(N)

    hist = get_historical_slice(frm, to)
    crisis_returns = hist[
        np.isin(
            np.arange(frm, to + 1),
            crisis_years
        )
    ]

    base_hits = sum(
        any(np.allclose(row, c) for c in crisis_returns)
        for row in base_series
    )

    crisis_hits = sum(
        any(np.allclose(row, c) for c in crisis_returns)
        for row in crisis_series
    )

    assert crisis_hits > base_hits
