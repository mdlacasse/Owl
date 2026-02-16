# Towards plugable rate models


Given the existing Plan/Rates structure, we want to design a plugin
system for rate generation that allows easy addition of new models
without modifying the core `Rates` class. This will enable experiments
with different rate generation techniques while maintaining the
integrity of the existing codebase.

Given:

- `Plan.setRates()`
- `Plan.regenRates()`
- Streamlit dynamic usage
- existing `Rates` class
- reproducibility control
- reverse/roll logic

We want a plugin system that:

1.  Preserves all current behavior
2.  Supports regenRates()
3.  Supports reproducibility
4.  Supports Streamlit interactive regeneration
5.  Avoids breaking existing tests
6.  Eventually allows legacy methods to migrate

Below is a clean, production-ready design aligned with your current
structure.

------------------------------------------------------------------------

# 🎯 Core Design Principle

**Plan owns orchestration. Rates owns legacy logic. Plugins own sequence
generation only.**

Do NOT mix plugin logic into `Rates`. Instead, create a unified “rate
engine” abstraction.

------------------------------------------------------------------------

# 🧱 Step 1 — Introduce a Base Interface

Create a new file:

    owlplanner/rate_models/base.py

``` python
from abc import ABC, abstractmethod
import numpy as np

class BaseRateModel(ABC):
    """
    All rate models must subclass this.
    """

    def __init__(self, N, seed=None, reproducible=False, **kwargs):
        self.N = N
        self.seed = seed
        self.reproducible = reproducible

    @abstractmethod
    def generate(self) -> np.ndarray:
        """
        Must return array shape (N, 4)
        Columns:
        [S&P 500, Corporate Baa, T Bonds, Inflation]
        All values must be decimal.
        """
        pass

    @property
    def needs_regen(self):
        """
        Whether regenRates() should regenerate this model.
        """
        return False
```

This replaces your `RATE_METHODS_NO_REGEN` logic for plugins.

------------------------------------------------------------------------

# 🧱 Step 2 — Wrap Legacy Rates as a Model

Create:

    owlplanner/rate_models/legacy.py

``` python
import numpy as np
from owlplanner import rates
from .base import BaseRateModel

class LegacyRateModel(BaseRateModel):

    def __init__(self, N, method, frm, to, values, stdev, corr,
                 seed=None, reproducible=False, override_reproducible=False,
                 **kwargs):
        super().__init__(N, seed, reproducible)

        self.method = method
        self.frm = frm
        self.to = to
        self.values = values
        self.stdev = stdev
        self.corr = corr
        self.override_reproducible = override_reproducible

    @property
    def needs_regen(self):
        return self.method not in rates.RATE_METHODS_NO_REGEN

    def generate(self):

        dr = rates.Rates(seed=self.seed)

        means, stdev, corr = dr.setMethod(
            self.method,
            self.frm,
            self.to,
            self.values,
            self.stdev,
            self.corr
        )

        series = dr.genSeries(self.N)

        return series
```

Now legacy methods are just another “model”.

------------------------------------------------------------------------

# 🧱 Step 3 — Plugin Loader

Create:

    owlplanner/rate_models/loader.py

``` python
import importlib.util
from pathlib import Path

def load_plugin(path):
    path = Path(path)

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "RateModel"):
        raise RuntimeError("Plugin must define class RateModel")

    return module.RateModel
```

------------------------------------------------------------------------

# 🧱 Step 4 — Modify Plan.setRates()

This is the critical pivot.

Replace your entire `setRates()` core logic with this structure:

``` python
def setRates(self, method, frm=None, to=None, values=None, stdev=None, corr=None,
             method_file=None,
             override_reproducible=False,
             reverse=False, roll=0):

    # ----------------------------------------
    # Seed logic (unchanged)
    # ----------------------------------------

    if method in ["stochastic", "histochastic"]:
        if self.reproducibleRates and not override_reproducible:
            if self.rateSeed is None:
                raise RuntimeError("Config error: reproducibleRates is True but rateSeed is None.")
            seed = self.rateSeed
        else:
            seed = int(time.time() * 1000000)
            if not override_reproducible:
                self.rateSeed = seed
    else:
        seed = None

    # ----------------------------------------
    # Model Selection
    # ----------------------------------------

    if method_file is not None:
        from owlplanner.rate_models.loader import load_plugin

        RateModel = load_plugin(method_file)

        model = RateModel(
            N=self.N_n,
            seed=seed,
            reproducible=self.reproducibleRates,
            method=method,
            frm=frm,
            to=to,
            values=values,
            stdev=stdev,
            corr=corr
        )
    else:
        from owlplanner.rate_models.legacy import LegacyRateModel

        model = LegacyRateModel(
            N=self.N_n,
            method=method,
            frm=frm,
            to=to,
            values=values,
            stdev=stdev,
            corr=corr,
            seed=seed,
            reproducible=self.reproducibleRates,
            override_reproducible=override_reproducible
        )

    # ----------------------------------------
    # Generate
    # ----------------------------------------

    series = model.generate()

    if series.shape != (self.N_n, 4):
        raise ValueError("Rate model returned incorrect shape.")

    self.tau_kn = series.transpose()

    # ----------------------------------------
    # Apply reverse / roll
    # ----------------------------------------

    if reverse or roll != 0:
        self.tau_kn = _apply_rate_sequence_transform(
            self.tau_kn, reverse, roll
        )

    # ----------------------------------------
    # Store state
    # ----------------------------------------

    self.rateMethod = method
    self.rateFrm = frm
    self.rateTo = to
    self.rateReverse = bool(reverse)
    self.rateRoll = int(roll)
    self._rateModel = model   # <-- critical for regenRates()

    # Build inflation multipliers
    self.gamma_n = _genGamma_n(self.tau_kn)

    self._adjustedParameters = False
    self.caseStatus = "modified"
```

------------------------------------------------------------------------

# 🧱 Step 5 — Modify regenRates()

Replace your current regen logic with:

``` python
def regenRates(self, override_reproducible=False):

    if not hasattr(self, "_rateModel"):
        return

    if not self._rateModel.needs_regen:
        return

    if self.reproducibleRates and not override_reproducible:
        return

    self.setRates(
        method=self.rateMethod,
        frm=self.rateFrm,
        to=self.rateTo,
        values=100 * self.rateValues if self.rateValues is not None else None,
        stdev=100 * self.rateStdev if self.rateStdev is not None else None,
        corr=self.rateCorr,
        override_reproducible=override_reproducible,
        reverse=self.rateReverse,
        roll=self.rateRoll
    )
```

Now regeneration is model-driven.

------------------------------------------------------------------------

# 🧠 Why This Works Beautifully With Streamlit

Streamlit can:

- Load plugin at runtime
- Regenerate via `regenRates()`
- Toggle reproducibility live
- Swap models without restarting

Because:

- Model is stored in `self._rateModel`
- No global state
- Seed controlled explicitly

------------------------------------------------------------------------

# 🚀 Future Benefits

You can now:

- Add Toeplitz
- Add Bootstrap
- Add ML models
- Add regime-switching
- Add scenario trees
- Add Bayesian updating
- Add macro-conditioned returns

Without touching `Rates.py`.

Eventually you can delete `Rates.py` entirely.

------------------------------------------------------------------------

# 🏁 Final Architecture

    Plan
     └── setRates()
          ├── LegacyRateModel (wraps rates.py)
          └── PluginRateModel (dynamic load)

    All models implement BaseRateModel

    regenRates() simply re-calls model.generate()

------------------------------------------------------------------------
