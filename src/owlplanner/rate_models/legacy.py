"""
Wrapper for legacy rate models.  All new rate models should subclass BaseRateModel.


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

###########################################################################
from owlplanner.rate_models.base import BaseRateModel
from owlplanner import rates


class LegacyRateModel(BaseRateModel):

    constant_methods = (
        "default",
        "optimistic",
        "conservative",
        "user",
        "historical average",
    )

    def __init__(self, config, seed=None, logger=None):
        super().__init__(config, seed, logger)

        self.method = config["method"]
        self.frm = config["frm"]
        self.to = config["to"]

        self._rates = rates.Rates(logger, seed=seed)

        self._rates.setMethod(
            self.method,
            self.frm,
            self.to,
            config.get("values"),
            config.get("stdev"),
            config.get("corr"),
        )

    @property
    def deterministic(self):
        # deterministic means no randomness
        return self.method in (
            "default",
            "optimistic",
            "conservative",
            "user",
            "historical average",
            "historical",
        )

    @property
    def constant(self):
        # constant means no time variation
        return self.method in self.constant_methods

    def generate(self, N):
        return self._rates.genSeries(N)
