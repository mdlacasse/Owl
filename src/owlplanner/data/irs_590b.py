"""
IRS Publication 590-B RMD lookup tables (effective 2022+).

Tables:
  - Table II  — Joint and Last Survivor Life Expectancy
  - Table III — Uniform Lifetime (divisors by owner age)

This module centralizes access to both tables for use in tax and RMD logic.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

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

from owlplanner.data.irs_590b_table_ii import JOINT_LIFE_TABLE  # noqa: F401

# ---------------------------------------------------------------------------
# Table III — Uniform Lifetime (divisors by owner age)
# ---------------------------------------------------------------------------

_UNIFORM_LIFETIME_BASE_AGE = 72
_UNIFORM_LIFETIME_DIVISORS = (
    27.4,
    26.5,
    25.5,
    24.6,
    23.7,
    22.9,
    22.0,
    21.1,
    20.2,
    19.4,
    18.5,
    17.7,
    16.8,
    16.0,
    15.2,
    14.4,
    13.7,
    12.9,
    12.2,
    11.5,
    10.8,
    10.1,
    9.5,
    8.9,
    8.4,
    7.8,
    7.3,
    6.8,
    6.4,
    6.0,
    5.6,
    5.2,
    4.9,
    4.6,
    4.3,
    4.1,
    3.9,
    3.7,
    3.5,
    3.4,
    3.3,
    3.1,
    3.0,
    2.9,
    2.8,
    2.7,
    2.5,
    2.3,
    2.0,
)

UNIFORM_LIFETIME_DIVISOR_BY_AGE = {_UNIFORM_LIFETIME_BASE_AGE + i: v for i, v in enumerate(_UNIFORM_LIFETIME_DIVISORS)}
