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
    DeltaBar_tn    -- shape (N_st, N_n) bracket widths (inflation-adjusted where brackets_indexed)
    sigmaBar_n     -- shape (N_n,) state standard deduction plus per-filer exemptions (each
                      inflation-adjusted where its flag says so;
                      zeros for a "federal" deduction, which the Plan fills in)
    re_cap_in      -- shape (N_i, N_n) retirement income exemption cap per individual, zero until
                      that individual meets exemption_age (0 = none, np.inf = fully exempt)
    pe_cap_in      -- shape (N_i, N_n) pension-only exemption cap per individual
                      (0 = pensions count toward re_cap_in instead)
    ss_thresh_n    -- shape (N_n,) AGI threshold below which SS is exempt (0 = not applicable)
    conv_ok_n      -- shape (N_n,) bool, whether Roth conversion income counts toward re_cap_in
    tax_ss_n       -- shape (N_n,) bool, whether the state taxes Social Security benefits
    pension_eligible_n -- shape (N_n,) bool, whether pensions share re_cap_in (no separate pension cap)
    fed_sd_n       -- shape (N_n,) bool, whether the state takes the federal standard deduction
    senior_bonus_n -- shape (N_n,) bool, whether that includes the OBBBA senior deduction
    credit_n       -- shape (N_n,) per-filer personal and senior credits, subtracted from the
                      state tax down to zero (see st_credits)
    recap_start_n  -- shape (N_n,) state AGI where benefit recapture begins (np.inf = none)
    recap_width_n  -- shape (N_n,) width of each phase-in, in AGI dollars
    recap_until_n  -- shape (N_n,) highest bracket threshold that starts a recapture tier
    rx_limit_kn    -- shape (N_rx, N_n) income ceilings of the income-tiered retirement exclusion
                      (NJ line 28a), lowest first; padding tiers have -inf
    rx_share_kn    -- shape (N_rx, N_n) share of eligible income excluded in each tier
    rx_cap_n       -- shape (N_n,) dollar cap on that exclusion (0 = the state has none)
    rx_age_n       -- shape (N_n,) age by December 31 at which a filer's income becomes eligible
    rx_earned_n    -- shape (N_n,) earned income at or below which the unused exclusion also covers
                      other income (NJ line 28b); -1 = no such extension

    The flag arrays are per year because the state can change during the plan.
    """

    N_st: int
    theta_tn: np.ndarray
    DeltaBar_tn: np.ndarray
    sigmaBar_n: np.ndarray
    re_cap_in: np.ndarray
    pe_cap_in: np.ndarray
    ss_thresh_n: np.ndarray
    conv_ok_n: np.ndarray
    tax_ss_n: np.ndarray
    pension_eligible_n: np.ndarray
    fed_sd_n: np.ndarray
    senior_bonus_n: np.ndarray
    credit_n: np.ndarray
    recap_start_n: np.ndarray
    recap_width_n: np.ndarray
    recap_until_n: np.ndarray
    rx_limit_kn: np.ndarray
    rx_share_kn: np.ndarray
    rx_cap_n: np.ndarray
    rx_age_n: np.ndarray
    rx_earned_n: np.ndarray


@lru_cache(maxsize=1)
def _load_state_data(toml_path: str = None) -> dict:
    """Load and cache taxes_state.toml. Returns the raw parsed dict."""
    path = toml_path or str(_TOML_PATH)
    with open(path, "r", encoding="utf-8") as f:
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


def _per_filer(entry: dict, key: str, state: str, *, with_age: bool = False):
    """Read a per-filer amount table ({amount, indexed[, age]}) from a TOML entry, or None.

    personal_exemption and senior_exemption are subtracted from state taxable income for each
    living filer (the senior one only from the year that filer reaches age); personal_credit is
    subtracted from the state tax itself. Each says whether its amount grows with inflation.
    """
    spec = entry.get(key)
    if spec is None:
        return None
    required = ("amount", "indexed", "age") if with_age else ("amount", "indexed")
    missing = [k for k in required if k not in spec]
    if missing or not isinstance(spec.get("indexed"), bool):
        raise ValueError(f"State '{state}': '{key}' needs {', '.join(required)} (indexed a boolean).")
    return spec


def _filers_alive(N_i: int, n_d: int, i_d, n: int) -> list:
    """Indices of the filers alive in plan year n: both until n_d, then the survivor."""
    if N_i == 1 or n < n_d:
        return list(range(N_i))
    if i_d is None:
        raise ValueError("i_d is required to tell which spouse survives after n_d.")
    return [(i_d + 1) % 2]


def _year_end_age(yob: int, mob: int, n: int) -> float:
    return date.today().year + n - yob + (12 - mob) / 12


def st_credits(
    state: str, N_i: int, n_d: int, N_n: int, gamma_n, *, yobs=None, mobs=None, i_d=None, toml_path=None
) -> np.ndarray:
    """Per-year state personal and senior credits (nominal $), subtracted from the state tax down to zero.

    personal_credit counts every living filer; senior_credit only those at or above its age by
    December 31, which needs yobs and mobs.
    """
    state = state.upper()
    entry = get_state_entry(state, 0, toml_path)
    pcr = _per_filer(entry, "personal_credit", state)
    scr = _per_filer(entry, "senior_credit", state, with_age=True)
    credit_n = np.zeros(N_n)
    if scr is not None and (yobs is None or mobs is None):
        raise ValueError(f"State '{state}' has a senior_credit: yobs and mobs are required.")
    for spec, aged in ((pcr, False), (scr, True)):
        if spec is None:
            continue
        g = np.asarray(gamma_n, dtype=float) if spec["indexed"] else np.ones(len(gamma_n))
        for n in range(N_n):
            alive = _filers_alive(N_i, n_d, i_d, n)
            count = sum(1 for i in alive if _year_end_age(yobs[i], mobs[i], n) >= spec["age"]) if aged else len(alive)
            credit_n[n] += float(spec["amount"]) * count * g[n]
    return credit_n


def _read_exclusion_tiers(entry: dict) -> list:
    """Read retirement_exclusion_tiers as [(income ceiling, share as a decimal), ...], lowest first."""
    tiers = entry.get("retirement_exclusion_tiers", [])
    out = [(float(lim), float(pct) / 100.0) for lim, pct in tiers]
    if any(b[0] <= a[0] for a, b in zip(out, out[1:])):
        raise ValueError(f"retirement_exclusion_tiers must have increasing income ceilings: {tiers}.")
    return out


def st_taxParams(
    state: str,
    N_i: int,
    n_d: int,
    N_n: int,
    gamma_n: np.ndarray,
    yobs: list,
    *,
    mobs: list,
    i_d=None,
    toml_path=None,
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
    StateTaxParams. Brackets, the deduction and the exemption caps each grow with gamma_n only
    where the entry's brackets_indexed, deduction_indexed and exemptions_indexed say so (#157).
    i_d (the first spouse to die) is needed for per-filer amounts when n_d < N_n.
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

    # --- Inflation indexing (issue #157) ---
    # Each component grows with gamma_n only where the state indexes it; a state that fixes
    # an amount in statute (NY's brackets, deduction and $20k exclusion) keeps it nominal.
    def _indexing(key):
        for entry in (entry_single, entry_mfj):
            if key not in entry:
                raise ValueError(f"State '{state}' is missing the required '{key}' field in taxes_state.toml.")
        return np.asarray(gamma_n, dtype=float) if entry_single[key] else np.ones(len(gamma_n))

    g_brackets = _indexing("brackets_indexed")
    g_deduction = _indexing("deduction_indexed")
    g_exemptions = _indexing("exemptions_indexed")

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
    tiers_s, tiers_m = _read_exclusion_tiers(entry_single), _read_exclusion_tiers(entry_mfj)
    N_rx = max(len(tiers_s), len(tiers_m), 1)
    rx_limit_kn = np.full((N_rx, N_n), -np.inf)
    rx_share_kn = np.zeros((N_rx, N_n))
    rx = np.tile(np.array([[0.0], [0.0], [-1.0]]), (1, N_n))  # cap, age, earned-income limit

    thisyear = date.today().year
    filing_status_n = filing_status_by_year(N_i, n_d, N_n)

    for n in range(N_n):
        entry = entry_mfj if filing_status_n[n] == 1 else entry_single
        theta_tn[:, n] = rates_m if filing_status_n[n] == 1 else rates_s
        DeltaBar_tn[:, n] = (widths_m if filing_status_n[n] == 1 else widths_s) * g_brackets[n]
        sigmaBar_n[n] = _deduction_amount(entry) * g_deduction[n]
        if "recapture_agi_start" in entry:
            # Recapture thresholds sit on the bracket schedule, so they index with the brackets.
            gb = g_brackets[n]
            recap[:, n] = [
                entry["recapture_agi_start"] * gb,
                entry.get("recapture_width", 50000.0) * gb,
                entry["recapture_until"] * gb,
            ]
        tiers = tiers_m if filing_status_n[n] == 1 else tiers_s
        if tiers:
            # The exclusion's ceilings and cap are exemption amounts.
            ge = g_exemptions[n]
            for k, (lim, share) in enumerate(tiers):
                rx_limit_kn[k, n] = lim * ge
                rx_share_kn[k, n] = share
            earned = entry.get("retirement_exclusion_earned_limit", -1)
            rx[:, n] = [
                entry["retirement_exclusion_cap"] * ge,
                entry.get("retirement_exclusion_age", 0),
                earned * ge if earned >= 0 else -1.0,
            ]

    # --- Per-filer exemptions, added to the state deduction for each living filer ---
    # personal_exemption applies at any age; senior_exemption from the year a filer reaches its
    # age (on December 31). Each grows with inflation only if it says so.
    pex = _per_filer(entry_single, "personal_exemption", state)
    sex = _per_filer(entry_single, "senior_exemption", state, with_age=True)
    if pex or sex:
        g_pex = np.asarray(gamma_n, dtype=float) if pex and pex["indexed"] else np.ones(len(gamma_n))
        g_sex = np.asarray(gamma_n, dtype=float) if sex and sex["indexed"] else np.ones(len(gamma_n))
        for n in range(N_n):
            alive = _filers_alive(N_i, n_d, i_d, n)
            if pex:
                sigmaBar_n[n] += float(pex["amount"]) * len(alive) * g_pex[n]
            if sex:
                seniors = sum(1 for i in alive if _year_end_age(yobs[i], mobs[i], n) >= sex["age"])
                sigmaBar_n[n] += float(sex["amount"]) * seniors * g_sex[n]

    # --- Retirement income exemption cap (per person; indexed only where the state indexes it) ---
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
    exemption_age = entry_single.get("exemption_age", 0)
    re_cap_in = np.zeros((N_i, N_n))
    pe_cap_in = np.zeros((N_i, N_n))

    if re_base > 0 or pe_base > 0:
        for i in range(N_i):
            for n in range(N_n):
                age = thisyear + n - yobs[i] + (12 - mobs[i]) / 12
                if exemption_age == 0 or age >= exemption_age:
                    re_cap_in[i, n] = np.inf if re_base == np.inf else re_base * g_exemptions[n]
                    pe_cap_in[i, n] = np.inf if pe_base == np.inf else pe_base * g_exemptions[n]

    # --- SS treatment ---
    # Use MFJ entry when couple; single entry otherwise. Both entries carry the same value
    # for all current states, but prefer the filing-status-appropriate entry for correctness.
    ss_entry = entry_mfj if N_i == 2 else entry_single
    tax_ss = bool(ss_entry["tax_social_security"])
    ss_thresh_base = float(ss_entry.get("ss_exemption_threshold", 0))
    ss_thresh_n = ss_thresh_base * g_exemptions[:N_n]

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
        conv_ok_n=flag(conv_ok),
        tax_ss_n=flag(tax_ss),
        pension_eligible_n=flag(pe_base == 0),
        fed_sd_n=flag(fed_sd),
        senior_bonus_n=flag(senior_bonus),
        credit_n=st_credits(state, N_i, n_d, N_n, gamma_n, yobs=yobs, mobs=mobs, i_d=i_d, toml_path=toml_path),
        recap_start_n=recap[0],
        recap_width_n=recap[1],
        recap_until_n=recap[2],
        rx_limit_kn=rx_limit_kn,
        rx_share_kn=rx_share_kn,
        rx_cap_n=rx[0],
        rx_age_n=rx[1],
        rx_earned_n=rx[2],
    )


def st_schedule(
    states_n: list, N_i: int, n_d: int, N_n: int, gamma_n: np.ndarray, yobs: list, *, mobs: list, i_d=None,
    toml_path=None,
) -> StateTaxParams:
    """State tax parameters when the state can differ from year to year.

    *states_n* holds the state in force in each year ("" = none), as returned by
    residence_by_year. Each column is taken from that state's own st_taxParams; the bracket
    dimension is padded to the longest schedule with zero-width top-rate brackets (#149). A year
    without a state gets one zero-rate bracket wide enough for any income. Upstream Owl's
    st_schedule (#159) returns the same arrays as a dict; this fork keeps them typed.
    """
    per_state = {
        s: st_taxParams(s, N_i, n_d, N_n, gamma_n, yobs, mobs=mobs, i_d=i_d, toml_path=toml_path)
        for s in sorted({s for s in states_n if s})
    }
    N_st = max((p.N_st for p in per_state.values()), default=1)

    theta_tn = np.zeros((N_st, N_n))
    DeltaBar_tn = np.zeros((N_st, N_n))
    sigmaBar_n = np.zeros(N_n)
    re_cap_in = np.zeros((N_i, N_n))
    pe_cap_in = np.zeros((N_i, N_n))
    ss_thresh_n = np.zeros(N_n)
    flag_names = ("conv_ok_n", "tax_ss_n", "pension_eligible_n", "fed_sd_n", "senior_bonus_n")
    flags = {name: np.zeros(N_n, dtype=bool) for name in flag_names}
    credit_n = np.zeros(N_n)
    recap = np.tile(np.array([[np.inf], [1.0], [0.0]]), (1, N_n))
    N_rx = max((p.rx_limit_kn.shape[0] for p in per_state.values()), default=1)
    rx_limit_kn = np.full((N_rx, N_n), -np.inf)
    rx_share_kn = np.zeros((N_rx, N_n))
    rx = np.tile(np.array([[0.0], [0.0], [-1.0]]), (1, N_n))

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
        credit_n[n] = p.credit_n[n]
        for name, arr in flags.items():
            arr[n] = getattr(p, name)[n]
        recap[:, n] = [p.recap_start_n[n], p.recap_width_n[n], p.recap_until_n[n]]
        k = p.rx_limit_kn.shape[0]
        rx_limit_kn[:k, n] = p.rx_limit_kn[:, n]
        rx_share_kn[:k, n] = p.rx_share_kn[:, n]
        rx[:, n] = [p.rx_cap_n[n], p.rx_age_n[n], p.rx_earned_n[n]]

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
        rx_limit_kn=rx_limit_kn,
        rx_share_kn=rx_share_kn,
        rx_cap_n=rx[0],
        rx_age_n=rx[1],
        rx_earned_n=rx[2],
        credit_n=credit_n,
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


def exclusion_share(income: float, limits: np.ndarray, shares: np.ndarray) -> float:
    """Share of eligible income an income-tiered retirement exclusion allows (NJ-1040 line 28a).

    The tier is the first whose ceiling *income* does not exceed; above the last ceiling nothing is
    excluded. The cliffs are the statute's: NJ's married filers with income of 100,000 exclude all of
    their eligible income up to the cap, and with 100,001 only half of it.
    """
    for lim, share in zip(limits, shares):
        if income <= lim:
            return float(share)
    return 0.0


def valid_states() -> list:
    """Return sorted list of valid two-letter state abbreviations."""
    data = load_state_data()
    return sorted({k.rsplit("_", 1)[0] for k in data})
