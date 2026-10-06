"""
Where the household lives in each plan year.

A residence is a state and, optionally, a locality within it (see tax_state and tax_local).
The household starts in one and may move to others in later years.

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

from __future__ import annotations

from typing import NamedTuple

from . import tax_local, tax_state


class Residence(NamedTuple):
    """From *year* on, the household lives in *state* ("" = a state with no income tax to model)."""

    year: int
    state: str
    locality: str = ""


def normalize(state: str, locality: str = "") -> tuple:
    """Return (state, locality) upper-cased, trimmed, validated and spelled as in the data files."""
    state = state.upper().strip() if state else ""
    if state and state not in tax_state.valid_states():
        raise ValueError(
            f"Unknown state '{state}'. Use a valid two-letter abbreviation from: {tax_state.valid_states()}"
        )
    if locality and not state:
        raise ValueError(f"Locality '{locality}' needs a state.")
    return state, tax_local.canonical_locality(state, locality or "")


def residence_by_year(state: str, locality: str, moves, first_year: int, N_n: int) -> list:
    """Return the (state, locality) in force in each of the N_n plan years.

    The residence on December 31 governs the whole year: there is no part-year split.
    *moves* is an iterable of Residence, tuples (year, state[, locality]) or dicts with those keys;
    each must fall after the first plan year and within the horizon, no year may appear twice, and
    each must change the residence. A move names
    the whole new residence, so its locality does not carry over from the old state.
    """
    by_year = [normalize(state, locality)] * N_n
    seen = set()
    for move in sorted(as_residence(m) for m in moves):
        year = move.year
        dest = (move.state, move.locality)
        if not first_year < year < first_year + N_n:
            raise ValueError(
                f"A move must fall after the first plan year and within the plan "
                f"({first_year + 1}-{first_year + N_n - 1}); got {year}."
            )
        if year in seen:
            raise ValueError(f"Two moves in {year}.")
        seen.add(year)
        if dest == by_year[year - first_year]:
            where = "the starting state" if dest == by_year[0] else "the residence it leaves"
            raise ValueError(f"The move in {year} goes to {where} ('{'/'.join(filter(None, dest))}').")
        by_year[year - first_year:] = [dest] * (N_n - (year - first_year))
    return by_year


def as_residence(move) -> Residence:
    """A move given as a Residence, a tuple (year, state[, locality]) or a dict with those keys."""
    if isinstance(move, dict):
        year, state, locality = move.get("year"), move.get("state"), move.get("locality", "")
    else:
        year, state, *rest = move
        locality = rest[0] if rest else ""
    try:
        year = int(year)
    except (TypeError, ValueError):
        raise ValueError(f"Year of the move must be a calendar year, got '{year}'.") from None
    return Residence(year, *normalize(state, locality))
