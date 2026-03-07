# `owlplanner/rate_models`

Pluggable rate model system for OWLPlanner.

This folder implements a modular, extensible architecture for generating
investment return and inflation rate series used by `Plan.setRates()`.

It supports:

* Original built-in methods (trailing-30, gaussian, historical, etc.)
* Built-in new models (e.g. `dataframe`)
* External plugin rate models loaded at runtime
* UI discovery of available models and required parameters



# Architecture Overview

```
rate_models/
├── base.py          # Abstract base class for all rate models
├── builtin.py       # Built-in methods (BuiltinRateModel shim + concrete classes)
├── dataframe.py     # Built-in DataFrame-based rate model
├── loader.py        # Model resolution and discovery system
└── README.md
```



# 1️⃣ Base Interface

All rate models must subclass:

```python
from owlplanner.rate_models.base import BaseRateModel
```

## Required Interface

```python
class BaseRateModel:

    def __init__(self, config, seed=None, logger=None):
        ...

    def generate(self, N) -> np.ndarray:
        """
        Must return array shape (N, 4)

        Columns:
        [S&P 500, Bonds Baa, T-Notes, Inflation]

        All values must be decimal (0.05 = 5%).
        """
```



## Optional Class Attributes

Use class attributes (not `@property`) so `get_metadata()` works correctly:

```python
deterministic = False  # True if model produces identical output for same inputs
constant = False     # True if time-constant rates (suppresses reverse/roll)
```

Default behavior:

* `deterministic = False`
* `constant = False`



# 2️⃣ Adding a New Plugin Rate Model

You can add new models in two ways:



## Option A — External Plugin File (Recommended)

Create a standalone Python file anywhere:

```python
# my_toeplitz_model.py

from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):

    model_name = "toeplitz_sor"

    description = """
    Toeplitz time-covariance sequence-of-returns model.
    Models autocorrelation across years.
    """

    required_parameters = {
        "means": {"type": "list[float]", "length": 4},
        "covariance": {"type": "matrix[4x4]"},
    }

    optional_parameters = {
        "lag_decay": {"type": "float", "default": 0.5},
    }

    def generate(self, N):

        means = np.array(self.config["means"])
        cov = np.array(self.config["covariance"])

        rng = np.random.default_rng(self.seed)

        return rng.multivariate_normal(means, cov, size=N)
```

Then use it:

```python
plan.setRates(
    method="toeplitz_sor",
    method_file="my_toeplitz_model.py",
    means=[0.07, 0.04, 0.03, 0.02],
    covariance=[[...]],
)
```



## Option B — Built-in Model (Internal Development)

Add a new file:

```
rate_models/toeplitz.py
```

Then modify `loader.py` to recognize the method name.



# 3️⃣ Using the Discovery System (For UI / Streamlit)

The loader exposes introspection helpers.

Import:

```python
from owlplanner.rate_models.loader import (
    list_available_rate_models,
    get_rate_model_metadata,
)
```



## List Available Models

```python
models = list_available_rate_models()

print(models)
# ['bootstrap_sor', 'conservative', 'dataframe', 'gaussian', 'garch_dcc', ...]
```



## Retrieve Model Metadata

```python
meta = get_rate_model_metadata("gaussian")

print(meta)
```

Example output:

```python
{
    "model_name": "gaussian",
    "description": "Random draws from multivariate normal distribution.",
    "required_parameters": {
        "values": {"type": "list[float]", "length": 4},
        "stdev": {"type": "list[float]", "length": 4},
    },
    "optional_parameters": {
        "corr": {"type": "matrix[4x4] or upper triangle"}
    }
}
```



## Retrieve Metadata for External Plugin

```python
meta = get_rate_model_metadata(
    "custom",
    method_file="my_toeplitz_model.py"
)
```



# 4️⃣ Built-in Models

Built-in methods are wrapped by `BuiltinRateModel` (backward-compatibility shim)
and implemented as concrete `BaseRateModel` subclasses.

Supported built-in methods:

```
trailing-30
optimistic
conservative
user
historical
historical average
gaussian
histogaussian
```

These automatically map to the old `rates.py` implementation.



# 5️⃣ Reverse and Roll Behavior

* Reverse and roll are applied in `Plan.setRates()`.
* Reverse/roll are ignored for:

  * `constant` models
  * models marked as deterministic and constant



# 6️⃣ Best Practices for New Models

When creating new models:

✔ Return `(N, 4)` numpy array
✔ Use decimal rates (0.07 not 7.0)
✔ Define `model_name`
✔ Define `description`
✔ Define `required_parameters`
✔ Define `optional_parameters`
✔ Support `seed` for reproducibility



# 7️⃣ Minimal Plugin Template

Copy/paste this to start a new model:

```python
from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):

    model_name = "my_model"

    description = "Describe your model here."

    required_parameters = {}
    optional_parameters = {}

    deterministic = False  # Use class attribute, not @property, for correct metadata
    constant = False

    def generate(self, N):
        return np.zeros((N, 4))
```



# 8️⃣ Testing a New Model

Example test:

```python
def test_plugin_model(tmp_path):

    plugin = tmp_path / "plugin.py"
    plugin.write_text("""
from owlplanner.rate_models.base import BaseRateModel
import numpy as np

class RateModel(BaseRateModel):
    def generate(self, N):
        return np.ones((N,4))*0.05
""")

    p = Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setRates(method="custom", method_file=str(plugin))

    assert np.allclose(p.tau_kn, 0.05)
```



# 9️⃣ Design Philosophy

The rate model system is designed to:

* Preserve legacy behavior
* Enable research experimentation
* Support future sequence-of-returns modeling
* Allow runtime plugin loading
* Enable UI introspection without hardcoding model knowledge
* Separate solver from rate generation



# 🔟 Future Extensions

Planned extensions include:

* Automatic plugin discovery from a folder
* Versioned rate models
* Validation schema for parameters
* Model capability flags (supports reverse? supports roll?)
* Structured parameter validation



# Summary

This folder provides a fully extensible, pluggable rate generation system.

To add a new rate model:

1. Subclass `BaseRateModel`
2. Implement `generate(N)`
3. Define metadata attributes
4. Use `method_file=` or register built-in in `loader.py`

Everything else integrates automatically with:

* `Plan.setRates`
* `Plan.regenRates`
* Config save/load
* Streamlit UI discovery

