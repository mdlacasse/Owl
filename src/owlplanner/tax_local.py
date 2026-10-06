"""
Local (city and county) income tax parameters for Owl retirement planner.

A locality sits on top of a state: its tax is either a graduated schedule on the state's
taxable income (New York City) or a percentage of the state's own tax (Yonkers). Data is
loaded from src/owlplanner/data/taxes_local.toml, which documents the format and how to add
a locality.

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

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import toml

from . import tax_state

_TOML_PATH = Path(__file__).parent / "data" / "taxes_local.toml"

_BASE_OF_TYPE = {"brackets": "state_taxable", "surcharge": "net_state_tax"}


@dataclass(frozen=True)
class LocalTaxParams:
    """Local income tax parameters for the LP.

    Attributes
    ----------
    N_lt        -- number of local brackets (0 when no locality has a bracket schedule)
    theta_tn    -- shape (N_lt, N_n) marginal rates (decimals) on state taxable income
    DeltaBar_tn -- shape (N_lt, N_n) bracket widths
    surcharge_n -- shape (N_n,) surcharge as a fraction of net state tax
    """

    N_lt: int
    theta_tn: np.ndarray
    DeltaBar_tn: np.ndarray
    surcharge_n: np.ndarray


@lru_cache(maxsize=1)
def _load_local_data(toml_path: str = None) -> dict:
    with open(toml_path or str(_TOML_PATH), "r", encoding="utf-8") as f:
        return toml.load(f)


def load_local_data(toml_path=None) -> dict:
    """Return the full taxes_local.toml as a dict (cached after first load)."""
    return _load_local_data(str(toml_path) if toml_path else None)


def _split_key(key: str):
    """'NY:NYC_MFJ' -> ('NY', 'NYC'); 'NY:Yonkers' -> ('NY', 'Yonkers')."""
    state, _, name = key.partition(":")
    for suffix in ("_MFJ", "_Single"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return state, name


def valid_localities(state: str, toml_path=None) -> list:
    """Return the sorted localities defined for *state*."""
    state = state.upper()
    return sorted({loc for st, loc in map(_split_key, load_local_data(toml_path)) if st == state})


def canonical_locality(state: str, locality: str, toml_path=None) -> str:
    """Return *locality* spelled as in the data file; "" stays "". Raise ValueError if unknown."""
    if not locality:
        return ""
    known = valid_localities(state, toml_path)
    for name in known:
        if name.lower() == locality.strip().lower():
            return name
    raise ValueError(f"Unknown locality '{locality}' for state '{state}'. Known: {known or 'none'}.")


def get_local_entry(state: str, locality: str, filing_status: int, toml_path=None) -> dict:
    """Return the TOML table for a locality, preferring the filing-status variant."""
    data = load_local_data(toml_path)
    base = f"{state.upper()}:{locality}"
    for key in (f"{base}_{'MFJ' if filing_status == 1 else 'Single'}", base):
        if key in data:
            return _checked(key, data[key])
    raise ValueError(f"No local tax table '{base}' in taxes_local.toml.")


def _checked(key: str, entry: dict) -> dict:
    kind = entry.get("type")
    if kind not in _BASE_OF_TYPE:
        raise ValueError(f"{key}: type must be 'brackets' or 'surcharge', got {kind!r}.")
    if entry.get("base") != _BASE_OF_TYPE[kind]:
        raise ValueError(f"{key}: a {kind} tax has base '{_BASE_OF_TYPE[kind]}', got {entry.get('base')!r}.")
    return entry


def local_taxParams(
    state: str, locality: str, N_i: int, n_d: int, N_n: int, gamma_n: np.ndarray, toml_path=None
) -> LocalTaxParams:
    """Local tax parameter arrays for one locality held for the whole plan."""
    return local_taxParams_schedule([(state, locality)] * N_n, N_i, n_d, N_n, gamma_n, toml_path)


def local_taxParams_schedule(
    residences_n: list, N_i: int, n_d: int, N_n: int, gamma_n: np.ndarray, toml_path=None
) -> LocalTaxParams:
    """Local tax parameters when the locality can differ from year to year.

    *residences_n* holds a (state, locality) pair for each year; locality "" means none.
    """
    status_n = tax_state.filing_status_by_year(N_i, n_d, N_n)
    per_year = []  # per year: (rates, widths) or None
    surcharge_n = np.zeros(N_n)
    for n, (state, locality) in enumerate(residences_n):
        if not locality:
            per_year.append(None)
            continue
        entry = get_local_entry(state, locality, int(status_n[n]), toml_path)
        if entry["type"] == "surcharge":
            surcharge_n[n] = float(entry["rate"]) / 100.0
            per_year.append(None)
            continue
        rates, widths = tax_state._brackets_to_rates_and_widths(entry["brackets"], tax_state._LAST_BRACKET_SENTINEL)
        gn = gamma_n[n] if entry.get("indexed", True) else 1.0
        widths = widths * gn
        widths[-1] = tax_state._LAST_BRACKET_SENTINEL * gamma_n[n]  # always room for the income
        per_year.append((rates, widths))

    N_lt = max((len(p[0]) for p in per_year if p is not None), default=0)
    theta_tn = np.zeros((N_lt, N_n))
    DeltaBar_tn = np.zeros((N_lt, N_n))
    for n, p in enumerate(per_year):
        if p is None:
            continue
        rates, widths = p
        theta_tn[: len(rates), n] = rates
        theta_tn[len(rates) :, n] = rates[-1]
        DeltaBar_tn[: len(rates), n] = widths
    return LocalTaxParams(N_lt=N_lt, theta_tn=theta_tn, DeltaBar_tn=DeltaBar_tn, surcharge_n=surcharge_n)
