"""
State income tax parameters for Owl retirement planner.

Provides st_taxParams(), which mirrors the interface of tax_federal.taxParams() but
returns state-specific bracket rates, widths, deductions, and exemption caps.
Data is loaded from src/owlplanner/data/taxes_state.toml.

Bracket rates in the TOML are stored as percentages (e.g. 5.35 = 5.35%);
st_taxParams converts them to decimals before returning.
"""
import tomllib
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
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_state_data(toml_path=None) -> dict:
    """Return the full taxes_state.toml as a dict (cached after first load)."""
    return _load_state_data(str(toml_path) if toml_path else None)


def get_state_entry(state: str, filing_status: int, toml_path=None) -> dict:
    """Return the TOML entry for *state* and *filing_status* (0=Single, 1=MFJ)."""
    data = load_state_data(toml_path)
    suffix = "MFJ" if filing_status == 1 else "Single"
    key = f"{state.upper()}_{suffix}"
    if key not in data:
        raise ValueError(f"Unknown state or filing status: '{key}'. "
                         f"Expected e.g. 'MN_Single' or 'MN_MFJ'.")
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


def st_taxParams(state: str, N_i: int, n_d: int, N_n: int,
                 gamma_n: np.ndarray, yobs: list,
                 toml_path=None) -> tuple:
    """Compute state income tax parameter arrays for the LP.

    Parameters
    ----------
    state   : two-letter US state abbreviation (e.g. 'MN')
    N_i     : number of individuals (1 or 2)
    n_d     : year index when first spouse dies (N_n if no transition)
    N_n     : number of plan years
    gamma_n : cumulative inflation multipliers, length N_n+1
    yobs    : list of birth years, length N_i
    toml_path : optional override for data file location (used in tests)

    Returns
    -------
    (N_st, st_theta_tn, st_DeltaBar_tn, st_sigmaBar_n,
     st_re_cap_n, st_pe_cap_n, st_tax_ss, st_ss_thresh_n)

    N_st           — number of state brackets (max across Single and MFJ)
    st_theta_tn    — shape (N_st, N_n) marginal rates (decimals)
    st_DeltaBar_tn — shape (N_st, N_n) inflation-adjusted bracket widths
    st_sigmaBar_n  — shape (N_n,) inflation-adjusted state standard deduction
    st_re_cap_n    — shape (N_n,) retirement income exemption cap per person
                     (0 = none, np.inf = fully exempt)
    st_pe_cap_n    — shape (N_n,) pension-only exemption cap per person
                     (0 = use st_re_cap_n for all retirement income)
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

    # --- Derive N_st (max brackets across both filing statuses) ---
    n_single = len(entry_single["brackets"])
    n_mfj = len(entry_mfj["brackets"])
    N_st = max(n_single, n_mfj)

    # --- Pre-compute base rates and widths for each filing status ---
    # Pad shorter bracket list with zero-width, zero-rate brackets at the end.
    def _pad(brackets, target_n):
        while len(brackets) < target_n:
            brackets.append([brackets[-1][0], 0.0])
        return brackets[:target_n]

    brackets_single = _pad(list(entry_single["brackets"]), N_st)
    brackets_mfj = _pad(list(entry_mfj["brackets"]) if N_i == 2 else
                        list(entry_single["brackets"]), N_st)

    rates_s, widths_s = _brackets_to_rates_and_widths(brackets_single, _LAST_BRACKET_SENTINEL)
    rates_m, widths_m = _brackets_to_rates_and_widths(brackets_mfj, _LAST_BRACKET_SENTINEL)

    # --- Build per-year arrays, switching filing status at n_d ---
    st_theta_tn = np.zeros((N_st, N_n))
    st_DeltaBar_tn = np.zeros((N_st, N_n))
    st_sigmaBar_n = np.zeros(N_n)

    thisyear = date.today().year
    filing_status = N_i - 1  # 1 = MFJ, 0 = Single

    for n in range(N_n):
        if n == n_d:
            filing_status = max(0, filing_status - 1)

        gn = gamma_n[n]
        if filing_status == 1:
            st_theta_tn[:, n] = rates_m
            st_DeltaBar_tn[:, n] = widths_m * gn
            st_sigmaBar_n[n] = entry_mfj["standard_deduction"] * gn
        else:
            st_theta_tn[:, n] = rates_s
            st_DeltaBar_tn[:, n] = widths_s * gn
            st_sigmaBar_n[n] = entry_single["standard_deduction"] * gn

    # --- Retirement income exemption cap (per person, inflation-adjusted) ---
    # Use the single-filer entry value (same per-person cap regardless of filing status).
    re_raw = entry_single["retirement_income_exemption"]
    re_base = np.inf if re_raw == -1 else float(re_raw)

    # Pension-only exemption cap
    pe_raw = entry_single.get("pension_exemption", 0)
    pe_base = np.inf if pe_raw == -1 else float(pe_raw)

    # Age gating: cap is zero until each year satisfies exemption_age for
    # the relevant individual(s). Use the older individual's age as a proxy
    # (conservative: exemption available as soon as any person qualifies).
    exemption_age = entry_single.get("exemption_age", 0)
    st_re_cap_n = np.zeros(N_n)
    st_pe_cap_n = np.zeros(N_n)

    if re_base > 0 or pe_base > 0:
        for n in range(N_n):
            year = thisyear + n
            # Check if at least one individual meets the age requirement.
            age_ok = (exemption_age == 0 or
                      any(year - yob >= exemption_age for yob in yobs))
            if age_ok:
                if re_base == np.inf:
                    st_re_cap_n[n] = np.inf
                else:
                    st_re_cap_n[n] = re_base * gamma_n[n]
                if pe_base == np.inf:
                    st_pe_cap_n[n] = np.inf
                else:
                    st_pe_cap_n[n] = pe_base * gamma_n[n]

    # --- SS treatment ---
    # Use MFJ entry when couple; single entry otherwise. Both entries carry the same value
    # for all current states, but prefer the filing-status-appropriate entry for correctness.
    ss_entry = entry_mfj if N_i == 2 else entry_single
    st_tax_ss = bool(ss_entry["tax_social_security"])
    ss_thresh_base = float(ss_entry.get("ss_exemption_threshold", 0))
    st_ss_thresh_n = np.array([ss_thresh_base * gamma_n[n] for n in range(N_n)])

    return (N_st, st_theta_tn, st_DeltaBar_tn, st_sigmaBar_n,
            st_re_cap_n, st_pe_cap_n, st_tax_ss, st_ss_thresh_n)


def valid_states() -> list:
    """Return sorted list of valid two-letter state abbreviations."""
    data = load_state_data()
    return sorted({k.rsplit("_", 1)[0] for k in data})
