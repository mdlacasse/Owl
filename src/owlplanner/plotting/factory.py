"""
Factory for creating plot backends.
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
