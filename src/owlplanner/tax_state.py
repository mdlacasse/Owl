"""
State income tax parameters for Owl retirement planner.

Provides st_taxParams(), which mirrors the interface of tax_federal.taxParams() but
returns state-specific bracket rates, widths, deductions, and exemption caps.
Data is loaded from src/owlplanner/data/taxes_state.toml.

Bracket rates in the TOML are stored as percentages (e.g. 5.35 = 5.35%);
st_taxParams converts them to decimals before returning.

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

import toml
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np

_TOML_PATH = Path(__file__).parent / "data" / "taxes_state.toml"

# Sentinel width for the last (open-ended) bracket, in base-year dollars.
# The optimizer fills lower brackets first (convex objective), so this
# only matters as a large-enough upper bound; 10x the top LTCG threshold is safe.
_LAST_BRACKET_SENTINEL = 5_000_000.0

# States with zero income tax — stored as single zero-rate bracket for uniformity.
NO_TAX_STATES = frozenset(["AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"])


@dataclass(frozen=True)
class StateTaxParams:
    """State income tax parameter arrays for the LP.

    Attributes
    ----------
    N_st           -- number of state brackets (max across Single and MFJ)
    theta_tn       -- shape (N_st, N_n) marginal rates (decimals)
    DeltaBar_tn    -- shape (N_st, N_n) bracket widths (inflation-adjusted when indexed)
    sigmaBar_n     -- shape (N_n,) state standard deduction (inflation-adjusted when indexed;
                      zeros for a "federal" deduction, which the Plan fills in)
    re_cap_in      -- shape (N_i, N_n) retirement income exemption cap per individual, zero until
                      that individual meets exemption_age (0 = none, np.inf = fully exempt)
    pe_cap_in      -- shape (N_i, N_n) pension-only exemption cap per individual
                      (0 = pensions count toward re_cap_in instead)
    ss_thresh_n    -- shape (N_n,) AGI threshold below which SS is exempt (0 = not applicable)
    conv_ok        -- shape (N_n,) bool, whether Roth conversion income counts toward re_cap_in
    tax_ss         -- shape (N_n,) bool, whether the state taxes Social Security benefits
    pe_pooled      -- shape (N_n,) bool, whether pensions share re_cap_in (no separate pension cap)
    fed_sd         -- shape (N_n,) bool, whether the state takes the federal standard deduction
    senior_bonus   -- shape (N_n,) bool, whether that includes the OBBBA senior deduction
    indexed        -- shape (N_n,) bool, whether brackets and dollar amounts scale with inflation
    recap_start_n  -- shape (N_n,) state AGI where benefit recapture begins (np.inf = none)
    recap_width_n  -- shape (N_n,) width of each phase-in, in AGI dollars
    recap_until_n  -- shape (N_n,) highest bracket threshold that starts a recapture tier

    The flag arrays are per year because the state can change during the plan.
    """

    N_st: int
    theta_tn: np.ndarray
    DeltaBar_tn: np.ndarray
    sigmaBar_n: np.ndarray
    re_cap_in: np.ndarray
    pe_cap_in: np.ndarray
    ss_thresh_n: np.ndarray
    conv_ok: np.ndarray
    tax_ss: np.ndarray
    pe_pooled: np.ndarray
    fed_sd: np.ndarray
    senior_bonus: np.ndarray
    indexed: np.ndarray
    recap_start_n: np.ndarray
    recap_width_n: np.ndarray
    recap_until_n: np.ndarray


@lru_cache(maxsize=1)
def _load_state_data(toml_path: str = None) -> dict:
    """Load and cache taxes_state.toml. Returns the raw parsed dict."""
    path = toml_path or str(_TOML_PATH)
    with open(path, "r") as f:
        return toml.load(f)


def load_state_data(toml_path=None) -> dict:
    """Return the full taxes_state.toml as a dict (cached after first load)."""
    return _load_state_data(str(toml_path) if toml_path else None)


def get_state_entry(state: str, filing_status: int, toml_path=None) -> dict:
    """Return the TOML entry for *state* and *filing_status* (0=Single, 1=MFJ)."""
    data = load_state_data(toml_path)
    suffix = "MFJ" if filing_status == 1 else "Single"
    key = f"{state.upper()}_{suffix}"
    if key not in data:
        raise ValueError(f"Unknown state or filing status: '{key}'. Expected e.g. 'MN_Single' or 'MN_MFJ'.")
    return data[key]


def _brackets_to_rates_and_widths(brackets: list, sentinel: float):
    """Convert [[lower, rate_pct], ...] to (rates, widths) arrays (decimal rates).

    rates  — 1-D array of marginal rates as decimals
    widths — 1-D array of bracket widths; last entry = sentinel
    """
    n = len(brackets)
    rates = np.array([b[1] / 100.0 for b in brackets])
    widths = np.empty(n)
    for i in range(n - 1):
        widths[i] = brackets[i + 1][0] - brackets[i][0]
    widths[-1] = sentinel
    return rates, widths


def _padded_rates_and_widths(brackets: list, n_st: int):
    """Like _brackets_to_rates_and_widths, padded to *n_st* entries.

    The open-ended top bracket keeps its sentinel width; padding entries repeat the top
    rate with zero width, so they can never take income from the real top bracket.
    Padding before converting would give the real top bracket zero width and the
    padding the open end (issue #149).
    """
    rates, widths = _brackets_to_rates_and_widths(brackets, _LAST_BRACKET_SENTINEL)
    extra = n_st - len(rates)
    return np.append(rates, np.full(extra, rates[-1])), np.append(widths, np.zeros(extra))


def filing_status_by_year(N_i: int, n_d: int, N_n: int) -> np.ndarray:
    """Filing status in each plan year: 1 = MFJ, 0 = Single (a couple files Single from year n_d on)."""
    status = np.full(N_n, N_i - 1, dtype=int)
    status[n_d:] = max(0, N_i - 2)
    return status


def _deduction_amount(entry: dict) -> float:
    """Dollar standard deduction of a TOML entry; 0 when it follows the federal one.

    A "federal" deduction is filled in by the Plan from the federal standard deduction,
    which depends on age and MAGI and so cannot be tabulated here.
    """
    sd = entry["standard_deduction"]
    return 0.0 if sd == "federal" else float(sd)


def federal_deduction(state: str, toml_path=None) -> tuple:
    """Return (uses_federal, with_senior_bonus) for *state*'s standard deduction.

    uses_federal      — the state allows the federal standard deduction, including the
                        additional amount for age 65+, rather than a fixed amount of its own
    with_senior_bonus — the state also allows the OBBBA $6,000 senior deduction
    """
    entry = get_state_entry(state, 0, toml_path)
    uses_federal = entry["standard_deduction"] == "federal"
    return uses_federal, uses_federal and bool(entry.get("senior_deduction", False))


def _read_indexed(entry: dict) -> bool:
    """Read the optional 'indexed' field (default True)."""
    val = entry.get("indexed", True)
    if not isinstance(val, bool):
        raise ValueError(f"Invalid indexed value '{val}': expected true or false.")
    return val


def st_taxParams(
    state: str, N_i: int, n_d: int, N_n: int, gamma_n: np.ndarray, yobs: list, *, mobs: list, toml_path=None
) -> StateTaxParams:
    """Compute state income tax parameter arrays for the LP.

    Parameters
    ----------
    state   : two-letter US state abbreviation (e.g. 'MN')
    N_i     : number of individuals (1 or 2)
    n_d     : year index when first spouse dies (N_n if no transition)
    N_n     : number of plan years
    gamma_n : cumulative inflation multipliers, length N_n+1
    yobs    : list of birth years, length N_i
    mobs    : list of birth months (1-12), length N_i; used for fractional exemption ages (59.5)
    toml_path : optional override for data file location (used in tests)

    Returns
    -------
    StateTaxParams, with dollar amounts scaled by gamma_n when the state is indexed (default)
    and held at nominal statutory dollars when the TOML entry says ``indexed = false``.
    """
    state = state.upper()
    data = load_state_data(toml_path)

    # --- Load entries for both filing statuses ---
    single_key = f"{state}_Single"
    mfj_key = f"{state}_MFJ"
    if single_key not in data:
        raise ValueError(f"State '{state}' not found in taxes_state.toml.")

    entry_single = data[single_key]
    entry_mfj = data[mfj_key] if mfj_key in data else entry_single

    # Both entries should agree; the single-filer value governs.
    indexed = _read_indexed(entry_single)

    # --- Derive N_st (max brackets across both filing statuses) ---
    n_single = len(entry_single["brackets"])
    n_mfj = len(entry_mfj["brackets"])
    N_st = max(n_single, n_mfj)

    # --- Pre-compute base rates and widths for each filing status ---
    brackets_mfj = entry_mfj["brackets"] if N_i == 2 else entry_single["brackets"]
    rates_s, widths_s = _padded_rates_and_widths(entry_single["brackets"], N_st)
    rates_m, widths_m = _padded_rates_and_widths(brackets_mfj, N_st)

    # --- Build per-year arrays, switching filing status at n_d ---
    theta_tn = np.zeros((N_st, N_n))
    DeltaBar_tn = np.zeros((N_st, N_n))
    sigmaBar_n = np.zeros(N_n)
    recap = np.tile(np.array([[np.inf], [1.0], [0.0]]), (1, N_n))  # start, width, until

    thisyear = date.today().year
    filing_status_n = filing_status_by_year(N_i, n_d, N_n)

    for n in range(N_n):
        gn = gamma_n[n] if indexed else 1.0
        entry = entry_mfj if filing_status_n[n] == 1 else entry_single
        theta_tn[:, n] = rates_m if filing_status_n[n] == 1 else rates_s
        DeltaBar_tn[:, n] = (widths_m if filing_status_n[n] == 1 else widths_s) * gn
        sigmaBar_n[n] = _deduction_amount(entry) * gn
        if "recapture_agi_start" in entry:
            recap[:, n] = [
                entry["recapture_agi_start"] * gn,
                entry.get("recapture_width", 50000.0) * gn,
                entry["recapture_until"] * gn,
            ]

    # --- Retirement income exemption cap (per person, inflation-adjusted) ---
    # Use the single-filer entry value (same per-person cap regardless of filing status).
    re_raw = entry_single["retirement_income_exemption"]
    re_base = np.inf if re_raw == -1 else float(re_raw)

    # Pension-only exemption cap
    pe_raw = entry_single.get("pension_exemption", 0)
    pe_base = np.inf if pe_raw == -1 else float(pe_raw)

    conv_ok = bool(entry_single.get("roth_conversion_eligible", True))

    # Age gating is per individual: each spouse qualifies on their own age, and an unused
    # cap cannot be claimed by the other spouse. An individual qualifies in the first year
    # in which they reach exemption_age (e.g. 59.5) by December 31.
    # The cap stays nominal when indexed = false (NY's $20k is statutory).
    exemption_age = entry_single.get("exemption_age", 0)
    re_cap_in = np.zeros((N_i, N_n))
    pe_cap_in = np.zeros((N_i, N_n))

    if re_base > 0 or pe_base > 0:
        for i in range(N_i):
            for n in range(N_n):
                age = thisyear + n - yobs[i] + (12 - mobs[i]) / 12
                if exemption_age == 0 or age >= exemption_age:
                    gn = gamma_n[n] if indexed else 1.0
                    re_cap_in[i, n] = np.inf if re_base == np.inf else re_base * gn
                    pe_cap_in[i, n] = np.inf if pe_base == np.inf else pe_base * gn

    # --- SS treatment ---
    # Use MFJ entry when couple; single entry otherwise. Both entries carry the same value
    # for all current states, but prefer the filing-status-appropriate entry for correctness.
    ss_entry = entry_mfj if N_i == 2 else entry_single
    tax_ss = bool(ss_entry["tax_social_security"])
    ss_thresh_base = float(ss_entry.get("ss_exemption_threshold", 0))
    ss_thresh_n = np.array([ss_thresh_base * (gamma_n[n] if indexed else 1.0) for n in range(N_n)])

    fed_sd, senior_bonus = federal_deduction(state, toml_path)

    def flag(value):
        return np.full(N_n, value, dtype=bool)

    return StateTaxParams(
        N_st=N_st,
        theta_tn=theta_tn,
        DeltaBar_tn=DeltaBar_tn,
        sigmaBar_n=sigmaBar_n,
        re_cap_in=re_cap_in,
        pe_cap_in=pe_cap_in,
        ss_thresh_n=ss_thresh_n,
        conv_ok=flag(conv_ok),
        tax_ss=flag(tax_ss),
        pe_pooled=flag(pe_base == 0),
        fed_sd=flag(fed_sd),
        senior_bonus=flag(senior_bonus),
        indexed=flag(indexed),
        recap_start_n=recap[0],
        recap_width_n=recap[1],
        recap_until_n=recap[2],
    )


def st_taxParams_schedule(
    states_n: list, N_i: int, n_d: int, N_n: int, gamma_n: np.ndarray, yobs: list, *, mobs: list, toml_path=None
) -> StateTaxParams:
    """State tax parameters when the state can differ from year to year.

    *states_n* holds the state in force in each year ("" = none), as returned by
    residence_by_year. Each column is taken from that state's own st_taxParams; the bracket
    dimension is padded to the longest schedule with zero-width top-rate brackets.
    """
    per_state = {
        s: st_taxParams(s, N_i, n_d, N_n, gamma_n, yobs, mobs=mobs, toml_path=toml_path)
        for s in sorted({s for s in states_n if s})
    }
    N_st = max((p.N_st for p in per_state.values()), default=1)

    theta_tn = np.zeros((N_st, N_n))
    DeltaBar_tn = np.zeros((N_st, N_n))
    sigmaBar_n = np.zeros(N_n)
    re_cap_in = np.zeros((N_i, N_n))
    pe_cap_in = np.zeros((N_i, N_n))
    ss_thresh_n = np.zeros(N_n)
    flags = {name: np.zeros(N_n, dtype=bool) for name in ("conv_ok", "tax_ss", "pe_pooled", "fed_sd", "senior_bonus")}
    flags["indexed"] = np.ones(N_n, dtype=bool)
    recap = np.tile(np.array([[np.inf], [1.0], [0.0]]), (1, N_n))

    for n, s in enumerate(states_n):
        if not s:
            DeltaBar_tn[0, n] = _LAST_BRACKET_SENTINEL * gamma_n[n]  # zero-rate placeholder: no state tax
            continue
        p = per_state[s]
        theta_tn[: p.N_st, n] = p.theta_tn[:, n]
        theta_tn[p.N_st :, n] = p.theta_tn[-1, n]
        DeltaBar_tn[: p.N_st, n] = p.DeltaBar_tn[:, n]
        sigmaBar_n[n] = p.sigmaBar_n[n]
        re_cap_in[:, n] = p.re_cap_in[:, n]
        pe_cap_in[:, n] = p.pe_cap_in[:, n]
        ss_thresh_n[n] = p.ss_thresh_n[n]
        for name, arr in flags.items():
            arr[n] = getattr(p, name)[n]
        recap[:, n] = [p.recap_start_n[n], p.recap_width_n[n], p.recap_until_n[n]]

    return StateTaxParams(
        N_st=N_st,
        theta_tn=theta_tn,
        DeltaBar_tn=DeltaBar_tn,
        sigmaBar_n=sigmaBar_n,
        re_cap_in=re_cap_in,
        pe_cap_in=pe_cap_in,
        ss_thresh_n=ss_thresh_n,
        recap_start_n=recap[0],
        recap_width_n=recap[1],
        recap_until_n=recap[2],
        **flags,
    )


def bracket_tax(ti: float, theta: np.ndarray, Delta: np.ndarray) -> float:
    """Tax on taxable income *ti* from one year's marginal rates and bracket widths."""
    lower = np.concatenate(([0.0], np.cumsum(Delta)[:-1]))
    return float(np.sum(theta * np.clip(ti - lower, 0.0, Delta)))


def state_recapture(
    agi: float, ti: float, theta: np.ndarray, Delta: np.ndarray, start: float, width: float, until: float,
    round_phase: bool = False,
) -> float:
    """Supplemental tax that takes back the benefit of the lower brackets (NY Tax Law sec. 601(d)).

    The state's tax on *ti* comes from the brackets; above state AGI *start* the benefit of paying
    less than the top rate on the lower slices is recaptured, in tiers:

    - The bracket that contains *start* gives the rate r1. While *ti* is below the next bracket
      threshold, the recapture is (r1 * ti - tax(ti)), phased in linearly as AGI rises from
      *start* to *start* + *width*.
    - Once *ti* reaches a higher bracket threshold L, with rate r and the rate below it r0, the
      recapture is the fully phased amount up to L, r0 * L - tax(L), plus (r - r0) * L phased in
      as AGI rises from L to L + *width*. The highest threshold that counts is *until*.

    This reproduces the constants on the IT-201-I tax computation worksheets (2025). *round_phase*
    rounds the phase-in fraction to four decimals, as the worksheets do.
    """
    if agi <= start:
        return 0.0

    def phase(x):
        f = min(max(x / width, 0.0), 1.0)
        return round(f, 4) if round_phase else f

    real = Delta > 0
    theta, Delta = theta[real], Delta[real]
    lower = np.concatenate(([0.0], np.cumsum(Delta)[:-1]))
    j0 = int(np.searchsorted(lower, start, side="right")) - 1  # bracket holding the start
    tiers = [k for k in range(j0 + 1, len(lower)) if lower[k] <= until]
    reached = [k for k in tiers if ti >= lower[k]]
    if not reached:
        return (theta[j0] * ti - bracket_tax(ti, theta, Delta)) * phase(agi - start)
    k = reached[-1]
    base = theta[k - 1] * lower[k] - bracket_tax(lower[k], theta, Delta)
    return base + (theta[k] - theta[k - 1]) * lower[k] * phase(agi - lower[k])


def valid_states() -> list:
    """Return sorted list of valid two-letter state abbreviations."""
    data = load_state_data()
    return sorted({k.rsplit("_", 1)[0] for k in data})
