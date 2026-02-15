
# 1️⃣ Basic IID Bootstrap

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1928
to = 2024
bootstrap_type = "iid"
```

### What It Tests

* Historical returns
* Historical cross-asset correlations
* Historical inflation behavior
* **No time dependence**
* No crisis clustering

Each retirement year is drawn independently from history.

This preserves:

* Fat tails
* Real joint stock/bond/inflation behavior

But destroys:

* Multi-year crashes
* Regime persistence
* Bear market clustering


### When to Use It

Use this when you want:

* A historically grounded alternative to Gaussian Monte Carlo
* Realistic tail behavior without regime modeling
* A baseline historical failure probability
* Quick sanity check of retirement robustness

This answers:

> “If history were shuffled randomly, how often would I fail?”


# 2️⃣ 5-Year Block Bootstrap

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1928
to = 2024
bootstrap_type = "block"
block_size = 5
```

### What It Tests

* Preserves 5-year local return patterns
* Keeps:

  * 1973–1974 collapse
  * 2000–2002 tech crash
  * 2008–2009 GFC
  * Inflation clusters
* Preserves momentum and regime behavior

This is a serious sequence-of-returns model.

### When to Use It

Use this when:

* Testing retirement start vulnerability
* Evaluating safe withdrawal rates
* Comparing fixed vs dynamic spending
* Measuring sequence clustering risk

This answers:

> “What if retirement includes real multi-year bear markets?”

If failure jumps materially compared to IID, your plan is sequence-sensitive.


# 3️⃣ Stationary Bootstrap (Expected 7-Year Regimes)

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1928
to = 2024
bootstrap_type = "stationary"
block_size = 7
```

### What It Tests

* Regime persistence
* Random block lengths
* Natural clustering without sharp block edges
* Smooth crisis transitions

Stationary bootstrap mimics how markets actually behave:

* Periods of bull
* Periods of stagflation
* Periods of bond stress
* Gradual regime changes

Expected regime length ≈ block_size.


### When to Use It

Use this when:

* You want realistic regime dynamics
* You suspect regime shifts matter
* You're evaluating long retirements (30–40 years)
* You want smoother crisis modeling than fixed blocks

This answers:

> “What if markets move in real regimes, not isolated bad years?”

This is often the most realistic bootstrap variant.


# 4️⃣ Circular Bootstrap

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1950
to = 2024
bootstrap_type = "circular"
block_size = 4
```

### What It Tests

* Regime clustering
* But allows blocks to wrap around dataset
* Prevents edge bias
* Allows post-2024 continuation to wrap to 1950

Circular bootstrap ensures:

* Equal probability of starting blocks anywhere
* No dataset truncation bias


### When to Use It

Use this when:

* You want full symmetry in historical sampling
* Avoiding edge effects matters
* You are using shorter historical windows
* You are doing academic-style stress modeling

It answers:

> “What if history were cyclic and could repeat seamlessly?”


# 5️⃣ Crisis Overweight Stress Test

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

### What It Tests

* Overweights:

  * Great Depression
  * 1970s stagflation
  * GFC
  * Modern inflation shock
* Increases probability of bad regimes
* Tests resilience under elevated crisis frequency

This is a stress-testing tool, not a base case.


### When to Use It

Use this when:

* You want conservative planning
* You worry future volatility may exceed historical frequency
* You want to test capital preservation strategy
* You want to simulate structural instability

This answers:

> “What if crises happen more often than history suggests?”

If your plan fails here but survives normal bootstrap:

You are **fragile to crisis clustering**, not average returns.


# 🎯 How These Map to Retirement Questions

| Question                                            | Best Model        |
| --------------------------------------------------- | ----------------- |
| Is my plan safe under normal historical randomness? | IID               |
| Am I vulnerable to 3–5 year bear markets?           | Block             |
| Do long regimes threaten me?                        | Stationary        |
| Is dataset boundary bias affecting results?         | Circular          |
| What if crises are more frequent going forward?     | Crisis overweight |


# 🧠 The Big Insight

Most retirement failures do NOT come from:

> Low average returns.

They come from:

> Early bad clustered returns.

Block and stationary bootstrap reveal that.

IID often understates risk.
Gaussian almost always understates risk.


# 🏁 Recommended Practical Workflow

1. Run Gaussian stochastic (baseline)
2. Run IID bootstrap
3. Run block bootstrap
4. Run crisis overweight
5. Compare failure rates

If failure jumps materially between IID and block:

You have sequence-clustering sensitivity.

If failure jumps materially with crisis overweight:

You are vulnerable to structural regime risk.

