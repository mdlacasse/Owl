"""
Bootstrap Sequence-of-Returns (SOR) rate model.

Advanced bootstrap model supporting:
- IID bootstrap
- Moving overlapping block bootstrap
- Circular block bootstrap
- Stationary bootstrap (Politis & Romano)
- Optional crisis overweighting

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
###################################################################
import numpy as np
import pandas as pd
import os
import sys

from owlplanner.rate_models.base import BaseRateModel
from owlplanner.rates import FROM, TO


class BootstrapSORRateModel(BaseRateModel):

    model_name = "bootstrap_sor"

    description = (
        "Historical bootstrap model for sequence-of-returns analysis. "
        "Supports IID, block, circular, and stationary bootstrap variants.  Defaults to IID."
    )

    more_info = "https://github.com/mdlacasse/Owl/blob/main/src/owlplanner/rate_models/bootstrap_sor.md"

    deterministic = False
    constant = False

    required_parameters = {
        "frm": {
            "type": "int",
            "description": "First historical year (inclusive).",
            "example": "1969",
        },
        "to": {
            "type": "int",
            "description": "Last historical year (inclusive).",
            "example": "2002",
        },
    }

    optional_parameters = {
        "bootstrap_type": {
            "type": "str",
            "description": "Type of bootstrap to perform. Defaults to iid",
            "allowed": ["iid", "block", "circular", "stationary"],
            "default": "iid",
            "example": '"block"',
        },
        "block_size": {
            "type": "int",
            "default": 1,
            "description": "Block length for block-based bootstraps.",
            "example": "5",
        },
        "crisis_years": {
            "type": "list[int]",
            "default": [],
            "description": "Years to overweight in sampling.",
            "example": "[1973, 1974, 2000, 2008]",
        },
        "crisis_weight": {
            "type": "float",
            "default": 1.0,
            "description": "Sampling multiplier for crisis years.",
            "example": "2.0",
        },
    }

    #######################################################################
    # Initialization
    #######################################################################

    def __init__(self, config, seed=None, logger=None):
        super().__init__(config, seed, logger)

        self.frm = int(self.get_param("frm"))
        self.to = int(self.get_param("to"))

        if not (FROM <= self.frm <= TO):
            raise ValueError(f"from={self.frm} out of bounds [{FROM}, {TO}].")

        if not (FROM <= self.to <= TO):
            raise ValueError(f"to={self.to} out of bounds [{FROM}, {TO}].")

        if self.frm > self.to:
            raise ValueError("from must be <= to.")

        self.bootstrap_type = self.get_param("bootstrap_type").lower()
        self.block_size = int(self.get_param("block_size"))
        self.crisis_years = self.get_param("crisis_years") or []
        self.crisis_weight = float(self.get_param("crisis_weight"))

        if self.block_size < 1:
            raise ValueError("block_size must be >= 1.")

        self._rng = np.random.default_rng(seed)

        self._historical_data, self._years = self._load_historical_slice()
        self._base_weights = self._build_sampling_weights()

    #######################################################################
    # Historical Data
    #######################################################################

    def _load_historical_slice(self):

        where = os.path.dirname(sys.modules["owlplanner"].__file__)
        file = os.path.join(where, "data/rates.csv")

        df = pd.read_csv(file)

        if "year" not in df.columns:
            raise ValueError("Historical rates.csv must contain a 'year' column.")

        mask = (df["year"] >= self.frm) & (df["year"] <= self.to)
        df_slice = df.loc[mask]

        if df_slice.empty:
            raise ValueError("No historical data in selected range.")

        years = df_slice["year"].values

        data = df_slice[["S&P 500", "Bonds Baa", "TNotes", "Inflation"]].values
        data = data / 100.0  # percent → decimal

        return data, years

    #######################################################################
    # Crisis Weighting
    #######################################################################

    def _build_sampling_weights(self):

        T = len(self._years)

        if not self.crisis_years or self.crisis_weight == 1.0:
            return None

        weights = np.ones(T, dtype=float)

        crisis_mask = np.isin(self._years, self.crisis_years)
        weights[crisis_mask] *= self.crisis_weight

        weights = np.clip(weights, 0.0, None)

        total = weights.sum()
        if total <= 0:
            raise ValueError("Crisis weighting produced zero probability mass.")

        weights /= total
        weights /= weights.sum()

        return weights

    #######################################################################
    # Sampling Utilities
    #######################################################################

    def _choice(self, n, probs):
        if probs is None:
            return self._rng.integers(0, n)
        return self._rng.choice(n, p=probs)

    #######################################################################
    # Generate
    #######################################################################

    def generate(self, N):

        if self.bootstrap_type == "iid":
            return self._iid_bootstrap(N)

        if self.bootstrap_type == "block":
            return self._block_bootstrap(N)

        if self.bootstrap_type == "circular":
            return self._circular_bootstrap(N)

        if self.bootstrap_type == "stationary":
            return self._stationary_bootstrap(N)

        raise ValueError(f"Unknown bootstrap_type '{self.bootstrap_type}'.")

    #######################################################################
    # IID Bootstrap
    #######################################################################

    def _iid_bootstrap(self, N):

        T = len(self._historical_data)

        if self._base_weights is None:
            idx = self._rng.integers(0, T, size=N)
        else:
            idx = self._rng.choice(T, size=N, replace=True, p=self._base_weights)

        return self._historical_data[idx]

    #######################################################################
    # Moving Block Bootstrap (Overlapping)
    #######################################################################

    def _block_bootstrap(self, N):

        T = len(self._historical_data)

        max_start = T - self.block_size + 1
        if max_start <= 0:
            raise ValueError("block_size larger than available historical window.")

        if self._base_weights is None:
            start_probs = None
        else:
            start_weights = self._base_weights[:max_start]
            start_weights = np.clip(start_weights, 0.0, None)
            start_weights /= start_weights.sum()
            start_probs = start_weights

        blocks = []
        total_len = 0

        while total_len < N:
            start = self._choice(max_start, start_probs)
            block = self._historical_data[start:start + self.block_size]
            blocks.append(block)
            total_len += len(block)

        series = np.vstack(blocks)
        return series[:N]

    #######################################################################
    # Circular Block Bootstrap
    #######################################################################

    def _circular_bootstrap(self, N):

        T = len(self._historical_data)

        blocks = []
        total_len = 0

        while total_len < N:
            start = self._choice(T, self._base_weights)
            idx = [(start + i) % T for i in range(self.block_size)]
            block = self._historical_data[idx]

            blocks.append(block)
            total_len += len(block)

        series = np.vstack(blocks)
        return series[:N]

    #######################################################################
    # Stationary Bootstrap (Politis & Romano)
    #######################################################################

    def _stationary_bootstrap(self, N):

        T = len(self._historical_data)
        p = 1.0 / self.block_size

        series = np.zeros((N, 4))

        idx = self._choice(T, self._base_weights)

        for t in range(N):
            series[t] = self._historical_data[idx]

            if self._rng.random() < p:
                idx = self._choice(T, self._base_weights)
            else:
                idx = (idx + 1) % T

        return series
