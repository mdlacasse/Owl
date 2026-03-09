## :orange[Available Rate Models]

The following rate models are available via the `method` field in `[rates_selection]`.

### :orange[Single-rate modes]

#### `conservative`

Pessimistic but plausible constant rates. Use for stress-testing worst-case scenarios.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"conservative"`) |

**Example:**

```toml
[rates_selection]
method = "conservative"
```

#### `historical average`

Constant rates equal to the geometric mean over the selected historical window.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"historical average"`) |
| `from` | Yes | int |  |
| `to` | Yes | int |  |

**Example:**

```toml
[rates_selection]
method = "historical average"
from = 1969
to = 2002
```

#### `optimistic`

Bullish constant rates based on industry forecasts for the next decade.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"optimistic"`) |

**Example:**

```toml
[rates_selection]
method = "optimistic"
```

#### `trailing-30`

Constant rates equal to the 30-year trailing geometric mean of annual returns. A long-run backward-looking assumption.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"trailing-30"`) |

**Example:**

```toml
[rates_selection]
method = "trailing-30"
```

#### `user`

Enter your own constant annual returns for each asset class below.

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
| `from` | Yes | int | Starting historical year (inclusive). |
| `to` | No | int | Ending historical year (inclusive). Defaults to frm if not provided. |

**Example:**

```toml
[rates_selection]
method = "historical"
from = 1969
```

### :orange[Stochastic models]

#### `bootstrap_sor`

Resamples actual historical years to build synthetic sequences, preserving fat tails and extreme events. Choose IID, block, circular, or stationary resampling strategy. [click here for more info](https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/bootstrap_sor.md)

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"bootstrap_sor"`) |
| `from` | Yes | int | First historical year (inclusive). |
| `to` | Yes | int | Last historical year (inclusive). |
| `bootstrap_type` | No | str | Type of bootstrap to perform. Defaults to iid |
| `block_size` | No | int | Block length for block-based bootstraps. |
| `crisis_years` | No | list[int] | Years to overweight in sampling. |
| `crisis_weight` | No | float | Sampling multiplier for crisis years. |

**Example:**

```toml
[rates_selection]
method = "bootstrap_sor"
from = 1969
to = 2002
```

#### `garch_dcc`

DCC-GARCH(1,1) model (Engle 2002) fitted by two-step MLE on historical data. Captures time-varying volatility (GARCH) and time-varying cross-asset correlations (DCC). Produces realistic volatility clustering and correlation spikes during market stress. [click here for more info](https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/README.md)

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"garch_dcc"`) |
| `from` | Yes | int | First year of historical window. |
| `to` | Yes | int | Last year of historical window. |

**Example:**

```toml
[rates_selection]
method = "garch_dcc"
from = 1928
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

#### `histogaussian`

Samples from a multivariate normal distribution fitted to the selected historical window. Parametric and Gaussian, parameters grounded in history.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"histogaussian"`) |
| `from` | Yes | int |  |
| `to` | Yes | int |  |

**Example:**

```toml
[rates_selection]
method = "histogaussian"
from = 1969
to = 2002
```

#### `histolognormal`

Fits a correlated log-normal model to the selected historical window and samples from it. Log-space parameters (mean and covariance of log-returns) are estimated directly from history. Returns are right-skewed and bounded below by -100%.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"histolognormal"`) |
| `from` | Yes | int |  |
| `to` | Yes | int |  |

**Example:**

```toml
[rates_selection]
method = "histolognormal"
from = 1928
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
| `from` | Yes | int | First historical year used for fitting (inclusive). |
| `to` | Yes | int | Last historical year used for fitting (inclusive). |
| `shrink` | No | bool | If True, apply spectral shrinkage to A when its spectral radius >= 0.95, ensuring stationarity. |

**Example:**

```toml
[rates_selection]
method = "var"
from = 1928
to = 2024
```

### :orange[DataFrame model]

#### `dataframe`

Sequential rates read from a pandas DataFrame (no year column). Programmatic use only — DataFrame cannot be serialized to TOML.

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
n_years = 40
```
