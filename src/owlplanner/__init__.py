"""
Owl planner package initialization and public API exports.

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

from owlplanner.plan import Plan                                              # noqa: F401
from owlplanner.plan import clone                                             # noqa: F401
from owlplanner.config import readConfig, saveConfig                          # noqa: F401
from owlplanner.rates import getRatesDistributions                            # noqa: F401
from owlplanner.version import __version__                                    # noqa: F401

# Make the package importable as 'owlplanner'
__all__ = ['Plan', 'clone', 'readConfig', 'getRatesDistributions', '__version__']
