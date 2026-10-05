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

import toml
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
) -> tuple:
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
    (N_st, st_theta_tn, st_DeltaBar_tn, st_sigmaBar_n,
     st_re_cap_in, st_pe_cap_in, st_conv_ok, st_tax_ss, st_ss_thresh_n)

    N_st           — number of state brackets (max across Single and MFJ)
    st_theta_tn    — shape (N_st, N_n) marginal rates (decimals)
    st_DeltaBar_tn — shape (N_st, N_n) inflation-adjusted bracket widths
    st_sigmaBar_n  — shape (N_n,) inflation-adjusted state standard deduction
                     (zeros for a "federal" deduction, which the Plan fills in)
    st_re_cap_in   — shape (N_i, N_n) retirement income exemption cap of each individual,
                     zero until that individual meets exemption_age
                     (0 = none, np.inf = fully exempt)
    st_pe_cap_in   — shape (N_i, N_n) pension-only exemption cap of each individual
                     (0 = pensions count toward st_re_cap_in instead)
    st_conv_ok     — bool, whether Roth conversion income counts toward st_re_cap_in
    st_tax_ss      — bool, whether state taxes Social Security benefits
    st_ss_thresh_n — shape (N_n,) AGI threshold below which SS is exempt
                     (0 = not applicable)
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
    # Pad the shorter schedule with zero-width brackets at the top rate, after its
    # open-ended bracket has kept the sentinel width. Padding before converting would
    # give the real top bracket zero width and the padding the open end (issue #149).
    def _padded_rates_and_widths(brackets, n_st):
        rates, widths = _brackets_to_rates_and_widths(brackets, _LAST_BRACKET_SENTINEL)
        extra = n_st - len(rates)
        return np.append(rates, np.full(extra, rates[-1])), np.append(widths, np.zeros(extra))

    rates_s, widths_s = _padded_rates_and_widths(entry_single["brackets"], N_st)
    rates_m, widths_m = _padded_rates_and_widths(
        entry_mfj["brackets"] if N_i == 2 else entry_single["brackets"], N_st
    )

    # --- Build per-year arrays, switching filing status at n_d ---
    st_theta_tn = np.zeros((N_st, N_n))
    st_DeltaBar_tn = np.zeros((N_st, N_n))
    st_sigmaBar_n = np.zeros(N_n)

    thisyear = date.today().year
    filing_status = N_i - 1  # 1 = MFJ, 0 = Single

    for n in range(N_n):
        if n == n_d:
            filing_status = max(0, filing_status - 1)

        if filing_status == 1:
            st_theta_tn[:, n] = rates_m
            st_DeltaBar_tn[:, n] = widths_m * g_brackets[n]
            st_sigmaBar_n[n] = _deduction_amount(entry_mfj) * g_deduction[n]
        else:
            st_theta_tn[:, n] = rates_s
            st_DeltaBar_tn[:, n] = widths_s * g_brackets[n]
            st_sigmaBar_n[n] = _deduction_amount(entry_single) * g_deduction[n]

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
                st_sigmaBar_n[n] += float(pex["amount"]) * len(alive) * g_pex[n]
            if sex:
                seniors = sum(1 for i in alive if _year_end_age(yobs[i], mobs[i], n) >= sex["age"])
                st_sigmaBar_n[n] += float(sex["amount"]) * seniors * g_sex[n]

    # --- Retirement income exemption cap (per person; indexed only where the state indexes it) ---
    # Use the single-filer entry value (same per-person cap regardless of filing status).
    re_raw = entry_single["retirement_income_exemption"]
    re_base = np.inf if re_raw == -1 else float(re_raw)

    # Pension-only exemption cap
    pe_raw = entry_single.get("pension_exemption", 0)
    pe_base = np.inf if pe_raw == -1 else float(pe_raw)

    st_conv_ok = bool(entry_single.get("roth_conversion_eligible", True))

    # Age gating is per individual: each spouse qualifies on their own age, and an unused
    # cap cannot be claimed by the other spouse. An individual qualifies in the first year
    # in which they reach exemption_age (e.g. 59.5) by December 31.
    exemption_age = entry_single.get("exemption_age", 0)
    st_re_cap_in = np.zeros((N_i, N_n))
    st_pe_cap_in = np.zeros((N_i, N_n))

    if re_base > 0 or pe_base > 0:
        for i in range(N_i):
            for n in range(N_n):
                age = thisyear + n - yobs[i] + (12 - mobs[i]) / 12
                if exemption_age == 0 or age >= exemption_age:
                    st_re_cap_in[i, n] = np.inf if re_base == np.inf else re_base * g_exemptions[n]
                    st_pe_cap_in[i, n] = np.inf if pe_base == np.inf else pe_base * g_exemptions[n]

    # --- SS treatment ---
    # Use MFJ entry when couple; single entry otherwise. Both entries carry the same value
    # for all current states, but prefer the filing-status-appropriate entry for correctness.
    ss_entry = entry_mfj if N_i == 2 else entry_single
    st_tax_ss = bool(ss_entry["tax_social_security"])
    ss_thresh_base = float(ss_entry.get("ss_exemption_threshold", 0))
    st_ss_thresh_n = ss_thresh_base * g_exemptions[:N_n]

    return (
        N_st, st_theta_tn, st_DeltaBar_tn, st_sigmaBar_n,
        st_re_cap_in, st_pe_cap_in, st_conv_ok, st_tax_ss, st_ss_thresh_n,
    )


def valid_states() -> list:
    """Return sorted list of valid two-letter state abbreviations."""
    data = load_state_data()
    return sorted({k.rsplit("_", 1)[0] for k in data})
