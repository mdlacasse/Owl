## :orange[Available Rate Models]

The following rate models are available via the `method` field in `[rates_selection]`.

### :orange[Single-rate modes]

#### `conservative`

Conservative fixed rate assumptions.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"conservative"`) |

**Example:**

```toml
[rates_selection]
method = "conservative"
```

#### `default`

30-year trailing historical average deterministic rates.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"default"`) |

**Example:**

```toml
[rates_selection]
method = "default"
```

#### `historical average`

Fixed rates equal to historical average over selected range.

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

Optimistic fixed rates based on industry forecasts.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"optimistic"`) |

**Example:**

```toml
[rates_selection]
method = "optimistic"
```

#### `user`

User-specified fixed annual rates (percent).

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

Historical year-by-year returns over selected range.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"historical"`) |
| `from` | Yes | int | Starting historical year (inclusive). |
| `to` | No | int | Ending historical year (inclusive). Defaults to `from` if not provided. |

**Example:**

```toml
[rates_selection]
method = "historical"
from = 1969
```

### :orange[Stochastic models]

#### `bootstrap_sor`

Historical bootstrap model for sequence-of-returns analysis. Supports IID, block, circular, and stationary bootstrap variants.  Defaults to IID. [click here for more info](https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/bootstrap_sor.md)

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

#### `histochastic`

Multivariate normal model using historical mean and covariance.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"histochastic"`) |
| `from` | Yes | int |  |
| `to` | Yes | int |  |

**Example:**

```toml
[rates_selection]
method = "histochastic"
from = 1969
to = 2002
```

#### `stochastic`

Multivariate normal stochastic model using user-provided mean and volatility.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"stochastic"`) |
| `values` | Yes | list[float] | Mean returns in percent. |
| `standard_deviations` | Yes | list[float] | Standard deviations in percent. |
| `correlations` | No | 4x4 matrix or list[6] | Pearson correlation coefficient (-1 to 1). Matrix or upper-triangle off-diagonals. Standard in finance/statistics. |

**Example:**

```toml
[rates_selection]
method = "stochastic"
values = [7.0, 4.5, 3.5, 2.5]
standard_deviations = [17.0, 8.0, 6.0, 2.0]
```

### :orange[DataFrame model]

#### `dataframe`

Sequential or year-based rates read from a pandas DataFrame.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `method` | Yes | str | model name (`"dataframe"`) |
| `df` | Yes | pandas.DataFrame | Must contain columns: ['S&P 500','Bonds Baa','T-Notes','Inflation'] |
| `n_years` | Yes | int | Number of years required for plan horizon. |
| `offset` | No | int | Number of initial rows to skip before reading sequentially. |
| `in_percent` | No | bool | If True (default), values are percent (7.0 = 7%) and divided by 100. Pass False if values are already decimal (0.07 = 7%). |
| `from` | No | int | Starting year (if year column present). |
| `to` | No | int | Ending year (if year column present). |

**Example:**

```toml
[rates_selection]
method = "dataframe"
df = "value"
n_years = 2000
```
