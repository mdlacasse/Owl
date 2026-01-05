"""
Factory for creating plot backend instances.

This module provides a factory class to create plot backends (matplotlib or
plotly) based on the specified backend type.

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

from .base import PlotBackend
from .matplotlib_backend import MatplotlibBackend
from .plotly_backend import PlotlyBackend


class PlotFactory:
    """Factory for creating plot backends."""

    @staticmethod
    def createBackend(backend_type: str) -> PlotBackend:
        """
        Create a plot backend of the specified type.

        Args:
            backend_type: Type of backend to create ("matplotlib" or "plotly")

        Returns:
            A PlotBackend instance

        Raises:
            ValueError: If backend_type is not a valid option
        """
        if backend_type == "matplotlib":
            return MatplotlibBackend()
        elif backend_type == "plotly":
            return PlotlyBackend()
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")
