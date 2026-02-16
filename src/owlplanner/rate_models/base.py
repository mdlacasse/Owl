"""
Base class for future rate models.


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
from abc import ABC, abstractmethod
import numpy as np


class BaseRateModel(ABC):
    """
    All rate models must subclass this.
    """

    model_name = "base"
    description = "Abstract rate model."
    required_parameters = {}
    optional_parameters = {}

    def __init__(self, config, seed=None, logger=None, **kwargs):
        self.config = config
        self.seed = seed
        self.logger = logger

    @abstractmethod
    def generate(self, N) -> np.ndarray:
        """
        Must return array shape (N, 4)
        Columns:
        [S&P 500, Corporate Baa, T Bonds, Inflation]
        All values must be decimal.
        """
        pass

    @property
    def deterministic(self):
        return False

    @property
    def constant(self):
        return False

    @classmethod
    def get_metadata(cls):
        return {
            "model_name": cls.model_name,
            "description": cls.description,
            "required_parameters": cls.required_parameters,
            "optional_parameters": cls.optional_parameters,
        }
