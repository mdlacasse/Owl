
# Bootstrap Sequence-of-Returns (bootstrap_sor)

## Overview

The `bootstrap_sor` model generates retirement return sequences using historical resampling techniques rather than parametric distributions (e.g., normal or lognormal models).

Unlike `stochastic` and `histochastic`, which assume multivariate normal returns, bootstrap SOR:

* Uses **actual historical return vectors**
* Preserves empirical cross-asset correlation
* Preserves fat tails and skewness
* Can preserve multi-year clustering
* Supports crisis overweighting

This makes it particularly well suited for:

* Sequence-of-returns risk analysis
* Stress testing retirement sustainability
* Tail-risk modeling
* Monte Carlo simulations grounded in history



# Core Idea

Let historical annual return vectors be:

```
R_t = [Stocks_t, Bonds_t, TNotes_t, Inflation_t]
```

for years `t = frm ... to`.

Bootstrap methods resample these historical vectors to build a synthetic return path of length `N`.

All bootstrap types:

* Operate on full 4-dimensional return vectors
* Preserve cross-asset correlation
* Return an `(N, 4)` array in decimal form



# Supported Bootstrap Types

The model supports four bootstrap types.



## 1. IID Bootstrap (`bootstrap_type = "iid"`)

**Independent yearly sampling with replacement.**

Each simulated year is drawn independently from the historical range.

### Properties

* Preserves marginal distributions
* Preserves cross-asset correlation
* Destroys serial correlation
* Fastest method

### When to Use

* Baseline historical Monte Carlo
* Quick stress testing
* When serial dependence is not critical



## 2. Moving Block Bootstrap (`bootstrap_type = "block"`)

**Overlapping fixed-length blocks.**

Instead of sampling single years, we sample contiguous historical blocks of length `block_size`.

Example with `block_size = 3`:

```
[1973, 1974, 1975]
[2000, 2001, 2002]
[2008, 2009, 2010]
```

Blocks are sampled with replacement until the requested horizon is filled.

### Properties

* Preserves short-term serial correlation
* Preserves volatility clustering
* Captures recession clustering
* Preserves regime persistence

### When to Use

* Sequence-of-returns research
* Volatility clustering modeling
* Realistic drawdown modeling



## 3. Circular Block Bootstrap (`bootstrap_type = "circular"`)

Similar to block bootstrap, but blocks are allowed to wrap around the historical dataset.

Example:

```
[2023, 2024, 1928]
```

### Properties

* Reduces edge bias
* Allows sampling from final years
* Useful when historical window is short

### When to Use

* Smaller historical ranges
* When edge bias matters



## 4. Stationary Bootstrap (`bootstrap_type = "stationary"`)

Based on Politis & Romano (1994).

Block lengths are random rather than fixed.

Probability of starting a new block:

```
p = 1 / block_size
```

Expected block length = `block_size`.

### Properties

* Preserves serial dependence
* Allows variable-length regimes
* More statistically flexible than fixed block

### When to Use

* Research-grade SOR modeling
* When fixed block length is too rigid
* When regime duration varies



# Crisis Overweighting

Optional parameters:

```
crisis_years = [1929, 1930, 1931, 2008, 2022]
crisis_weight = 3.0
```

This increases the probability that crisis years are selected as block starting points.

Effect:

* Increases frequency of extreme events
* Preserves historical crisis magnitudes
* Enables stress testing without parametric distortion

If `crisis_weight = 1.0` (default), no overweighting occurs.



# Parameters

## Required

| Parameter | Type | Description                       |
| --------- | ---- | --------------------------------- |
| `frm`     | int  | First historical year (inclusive) |
| `to`      | int  | Last historical year (inclusive)  |



## Optional

| Parameter        | Type      | Default | Description                      |
| ---------------- | --------- | ------- | -------------------------------- |
| `bootstrap_type` | str       | `"iid"` | iid, block, circular, stationary |
| `block_size`     | int       | 1       | Block length                     |
| `crisis_years`   | list[int] | []      | Years to overweight              |
| `crisis_weight`  | float     | 1.0     | Sampling multiplier              |



# Determinism and Regeneration

* `bootstrap_sor` is **stochastic**
* Regenerates on `regenRates()` unless reproducibility is enabled
* Honors Plan-level seed handling

# TOML Examples



## 1️⃣ Basic IID Bootstrap

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1928
to = 2024
bootstrap_type = "iid"
```



## 2️⃣ 5-Year Block Bootstrap

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1928
to = 2024
bootstrap_type = "block"
block_size = 5
```



## 3️⃣ Stationary Bootstrap (Expected 7-Year Regimes)

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1928
to = 2024
bootstrap_type = "stationary"
block_size = 7
```



## 4️⃣ Circular Bootstrap

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1950
to = 2024
bootstrap_type = "circular"
block_size = 4
```



## 5️⃣ Crisis Overweight Stress Test

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1928
to = 2024
bootstrap_type = "block"
block_size = 4

crisis_years = [1929, 1930, 1931, 1973, 1974, 2008, 2022]
crisis_weight = 3.0
```



# Comparison vs Other Rate Methods

| Method                     | Parametric                | Preserves Tails | Preserves Serial Corr | Preserves Cross Corr |
| -------------------------- | ------------------------- | --------------- | --------------------- | -------------------- |
| stochastic                 | Yes (Normal)              | ❌               | ❌                     | ✅                    |
| histochastic               | Yes (Normal, hist params) | ❌               | ❌                     | ✅                    |
| historical                 | No                        | ✅               | ✅                     | ✅                    |
| bootstrap_sor (iid)        | No                        | ✅               | ❌                     | ✅                    |
| bootstrap_sor (block)      | No                        | ✅               | ✅                     | ✅                    |
| bootstrap_sor (stationary) | No                        | ✅               | ✅                     | ✅                    |



# Recommended Defaults

For most retirement Monte Carlo studies:

```
bootstrap_type = "stationary"
block_size = 5
```

This captures regime persistence without overfitting block length.



# Performance Notes

* Computational cost is low
* No matrix decompositions required
* Complexity ≈ O(N)

Suitable for large Monte Carlo sweeps.



# Future Extensions (Planned)

* Regime-aware bootstrap
* Conditional bootstrap (inflation-driven)
* Heavy-tail bootstrap
* Copula bootstrap
* Crisis-only stress paths
* Hybrid Toeplitz-bootstrap models



# Summary

`bootstrap_sor` provides:

* Non-parametric Monte Carlo
* Realistic historical tail risk
* Optional serial dependence modeling
* Crisis stress testing capability
* Fully compatible with OWL’s plugin architecture


