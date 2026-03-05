## :orange[Available Rate Models]

The following rate models are available via the `method` field in `[rates_selection]`.

### :orange[Single-rate modes]

#### `conservative`

Pessimistic but plausible fixed rates. Use for stress-testing worst-case scenarios.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"conservative"`) |

**Example:**

```toml
[rates_selection]
method = "conservative"
```

#### `trailing-30`

Fixed rates equal to the 30-year trailing historical average. A reasonable middle-ground assumption.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"trailing-30"`) |

**Example:**

```toml
[rates_selection]
method = "trailing-30"
```

#### `historical average`

Fixed rates equal to the arithmetic mean over the selected historical window.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"historical average"`) |
| `frm` | Yes | int |  |
| `to` | Yes | int |  |

**Example:**

```toml
[rates_selection]
method = "historical average"
frm = 1969
to = 2002
```

#### `optimistic`

Bullish fixed rates based on industry forecasts for the next decade.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"optimistic"`) |

**Example:**

```toml
[rates_selection]
method = "optimistic"
```

#### `user`

Enter your own fixed annual returns for each asset class below.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"user"`) |
| `values` | Yes | list[float] | Rates in percent: [S&P 500, Bonds Baa, T-Notes, Inflation] |

**Example:**

```toml
[rates_selection]
method = "user"
values = [7.0, 4.5, 3.5, 2.5]
```

### :orange[Deterministic models]

#### `historical`

Replays the exact year-by-year returns from the historical window in order. Deterministic — best for backtesting.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"historical"`) |
| `frm` | Yes | int | Starting historical year (inclusive). |
| `to` | No | int | Ending historical year (inclusive). Defaults to frm if not provided. |

**Example:**

```toml
[rates_selection]
method = "historical"
frm = 1969
```

### :orange[Stochastic models]

#### `bootstrap_sor`

Resamples actual historical years to build synthetic sequences, preserving fat tails and extreme events. Choose IID, block, circular, or stationary resampling strategy. [click here for more info](https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/bootstrap_sor.md)

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"bootstrap_sor"`) |
| `frm` | Yes | int | First historical year (inclusive). |
| `to` | Yes | int | Last historical year (inclusive). |
| `bootstrap_type` | No | str | Type of bootstrap to perform. Defaults to iid |
| `block_size` | No | int | Block length for block-based bootstraps. |
| `crisis_years` | No | list[int] | Years to overweight in sampling. |
| `crisis_weight` | No | float | Sampling multiplier for crisis years. |

**Example:**

```toml
[rates_selection]
method = "bootstrap_sor"
frm = 1969
to = 2002
```

#### `garch_dcc`

DCC-GARCH(1,1) model (Engle 2002) fitted by two-step MLE on historical data. Captures time-varying volatility (GARCH) and time-varying cross-asset correlations (DCC). Produces realistic volatility clustering and correlation spikes during market stress. [click here for more info](https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/README.md)

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"garch_dcc"`) |
| `frm` | Yes | int | First year of historical window. |
| `to` | Yes | int | Last year of historical window. |

**Example:**

```toml
[rates_selection]
method = "garch_dcc"
frm = 1928
to = 2024
```

#### `gaussian`

Samples from a multivariate normal (Gaussian) distribution with means, volatilities, and correlations you specify below.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"gaussian"`) |
| `values` | Yes | list[float] | Mean returns in percent. |
| `stdev` | Yes | list[float] | Standard deviations in percent. |
| `corr` | No | 4x4 matrix or list[6] | Pearson correlation coefficient (-1 to 1). Matrix or upper-triangle off-diagonals. Standard in finance/statistics. |

**Example:**

```toml
[rates_selection]
method = "gaussian"
values = [7.0, 4.5, 3.5, 2.5]
stdev = [17.0, 8.0, 6.0, 2.0]
```

#### `histochastic`

Samples from a multivariate normal distribution fitted to the selected historical window. Parametric and Gaussian, parameters grounded in history.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"histochastic"`) |
| `frm` | Yes | int |  |
| `to` | Yes | int |  |

**Example:**

```toml
[rates_selection]
method = "histochastic"
frm = 1969
to = 2002
```

#### `histolognormal`

Fits a correlated log-normal model to the selected historical window and samples from it. Log-space parameters (mean and covariance of log-returns) are estimated directly from history. Returns are right-skewed and bounded below by -100%.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"histolognormal"`) |
| `frm` | Yes | int |  |
| `to` | Yes | int |  |

**Example:**

```toml
[rates_selection]
method = "histolognormal"
frm = 1928
to = 2024
```

#### `lognormal`

Samples from a correlated log-normal distribution with arithmetic means, volatilities, and correlations you specify below. Log-normal returns are strictly bounded below by -100% and are right-skewed, consistent with Geometric Brownian Motion theory.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"lognormal"`) |
| `values` | Yes | list[float] | Arithmetic mean returns in percent. |
| `stdev` | Yes | list[float] | Standard deviations in percent. |
| `corr` | No | 4x4 matrix or list[6] | Pearson correlation coefficient (-1 to 1). Matrix or upper-triangle off-diagonals. Standard in finance/statistics. |

**Example:**

```toml
[rates_selection]
method = "lognormal"
values = [7.0, 4.5, 3.5, 2.5]
stdev = [17.0, 8.0, 6.0, 2.0]
```

#### `var`

VAR(1) model fitted by Ordinary Least Squares (OLS) on the historical window. Captures momentum and mean-reversion — each year's returns depend on the previous year across all four asset classes. [click here for more info](https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/README.md)

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"var"`) |
| `frm` | Yes | int | First historical year used for fitting (inclusive). |
| `to` | Yes | int | Last historical year used for fitting (inclusive). |
| `shrink` | No | bool | If True, apply spectral shrinkage to A when its spectral radius >= 0.95, ensuring stationarity. |

**Example:**

```toml
[rates_selection]
method = "var"
frm = 1928
to = 2024
```

### :orange[DataFrame model]

#### `dataframe`

Sequential rates read from a pandas DataFrame (no year column).

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"dataframe"`) |
| `df` | Yes | pandas.DataFrame | Must contain columns: ['S&P 500','Bonds Baa','T-Notes','Inflation'] |
| `n_years` | Yes | int | Number of years (rows) required for plan horizon. |
| `offset` | No | int | Number of initial rows to skip before reading sequentially. |
| `in_percent` | No | bool | If True (default), DataFrame values are in percent (e.g. 7.0 = 7%) and are divided by 100 internally. Pass False if values are already in decimal (e.g. 0.07 = 7%). |

**Example:**

```toml
[rates_selection]
method = "dataframe"
df = "value"
n_years = 2000
```
