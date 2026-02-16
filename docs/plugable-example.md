# Plugable example


for this example, we’ll replace the legacy hard-coded `user` method that
took fixed rates from the config:

``` toml
method = "user"
values = [7.0, 4.0, 3.0, 2.5]
```

with a plugin-based implementation using `BaseRateModel`.

This demonstrates:

- how a simple deterministic model works
- how reproducibility is irrelevant
- how it cleanly fits the new interface
- how it removes logic from `Rates.py`

------------------------------------------------------------------------

# 📁 File Structure

    owlplanner/
        rate_models/
            base.py
            user_fixed.py

------------------------------------------------------------------------

# 🧱 base.py (unchanged)

``` python
# owlplanner/rate_models/base.py

from abc import ABC, abstractmethod
import numpy as np

class BaseRateModel(ABC):

    def __init__(self, N, seed=None, reproducible=False, **kwargs):
        self.N = N
        self.seed = seed
        self.reproducible = reproducible

    @abstractmethod
    def generate(self) -> np.ndarray:
        """
        Must return array shape (N, 4)
        Decimal values.
        """
        pass

    @property
    def needs_regen(self):
        return False
```

------------------------------------------------------------------------

# 📁 user_fixed.py

``` python
# owlplanner/rate_models/user_fixed.py

import numpy as np
from .base import BaseRateModel


class RateModel(BaseRateModel):
    """
    Fixed user-specified rates.
    Replaces method="user".
    """

    def __init__(self, N, values=None, **kwargs):
        super().__init__(N, **kwargs)

        if values is None:
            raise ValueError("UserFixedRateModel requires 'values' parameter.")

        if len(values) != 4:
            raise ValueError("values must contain 4 entries.")

        # Convert percent → decimal
        self._rates = np.array(values, dtype=float) / 100.0

    def generate(self) -> np.ndarray:
        """
        Returns deterministic Nx4 rate matrix.
        """
        return np.tile(self._rates, (self.N, 1))

    @property
    def needs_regen(self):
        return False
```

------------------------------------------------------------------------

# 🧠 What This Replaces

Old `Rates.setMethod("user")`:

``` python
elif method == "user":
    self.means = np.array(values, dtype=float)
    self.means /= 100.0
    self._setFixedRates(self.means)
```

Now the logic is entirely isolated inside a clean model.

------------------------------------------------------------------------

# 📄 Example TOML

``` toml
[rates_selection]
method = "user"
method_file = "owlplanner/rate_models/user_fixed.py"

values = [7.0, 4.0, 3.0, 2.5]
reverse_sequence = false
roll_sequence = 0
```

------------------------------------------------------------------------

# 🔁 How Plan.setRates() Uses It

Inside your new plugin-aware `setRates()`:

``` python
if method_file is not None:
    from owlplanner.rate_models.loader import load_plugin

    RateModel = load_plugin(method_file)

    model = RateModel(
        N=self.N_n,
        seed=seed,
        reproducible=self.reproducibleRates,
        values=values
    )
```

Then:

``` python
series = model.generate()
self.tau_kn = series.transpose()
```

------------------------------------------------------------------------

# 🧪 What Happens at Runtime

If:

    values = [7.0, 4.0, 3.0, 2.5]
    N = 5

`generate()` returns:

    [[0.07  0.04  0.03  0.025]
     [0.07  0.04  0.03  0.025]
     [0.07  0.04  0.03  0.025]
     [0.07  0.04  0.03  0.025]
     [0.07  0.04  0.03  0.025]]

Exactly what legacy `user` produced.

------------------------------------------------------------------------

# 🧩 Why This Is Architecturally Powerful

This demonstrates:

| Legacy Design         | Plugin Design                   |
|-----------------------|---------------------------------|
| Big if/elif tree      | One class per model             |
| Hard-coded methods    | Drop-in pluggable               |
| Shared mutable state  | Isolated model state            |
| Regen logic scattered | Model decides via `needs_regen` |
| Hard to extend        | Infinite extensibility          |

------------------------------------------------------------------------

# 🚀 Next Natural Migration

Once this works:

- Move `"default"`
- Move `"optimistic"`
- Move `"conservative"`
- Move `"historical average"`

Eventually:

Delete most of `Rates.setMethod()` entirely.

------------------------------------------------------------------------

# 🏁 Final Result

You now have:

- A research-ready architecture
- Clean separation of concerns
- Runtime pluggability
- Streamlit-safe regeneration
- Testable individual rate engines
