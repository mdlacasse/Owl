"""
JSON output formatter for solved Plan objects.

Converts a solved Plan to a structured dict suitable for JSON serialization.
All monetary values are in nominal dollars unless the key ends with ``_today``
or ``_today_dollars``.

Copyright (C) 2025-2026 The Owl Authors
"""

import json
import numpy as np

from owlplanner.export import plan_metrics


class _NumpyEncoder(json.JSONEncoder):
    """Serialize numpy scalar types that the default encoder rejects."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def _round(val, decimals=0):
    """Round a numpy scalar to a Python int or float."""
    if decimals == 0:
        return int(round(float(val)))
    return round(float(val), decimals)


def _metrics_to_summary(m: dict) -> dict:
    """
    Translate plan_metrics() snake_case float dict to the JSON summary block.

    Renames keys for JSON clarity (e.g. ``_today`` → ``_today_dollars``,
    explicit ``_nominal`` suffix) and rounds all monetary values to integers.
    """
    def r(key):
        return int(round(m[key]))

    return {
        "spending_basis_today_dollars":          r("spending_basis"),
        "effective_tax_rate":                    round(m["effective_tax_rate"], 4),
        "total_spending_nominal":                r("total_spending_nominal"),
        "total_spending_today_dollars":          r("total_spending_today"),
        "total_fixed_income_nominal":            r("total_fixed_income_nominal"),
        "total_fixed_income_today_dollars":      r("total_fixed_income_today"),
        "ss_income_nominal":                     r("ss_income_nominal"),
        "ss_income_today_dollars":               r("ss_income_today"),
        "pension_income_nominal":                r("pension_income_nominal"),
        "pension_income_today_dollars":          r("pension_income_today"),
        "spia_income_nominal":                   r("spia_income_nominal"),
        "wages_nominal":                         r("wages_nominal"),
        "roth_conversions_nominal":              r("roth_conversions_nominal"),
        "roth_conversions_today_dollars":        r("roth_conversions_today"),
        "federal_income_tax_nominal":            r("federal_income_tax_nominal"),
        "federal_income_tax_today_dollars":      r("federal_income_tax_today"),
        "ltcg_tax_nominal":                      r("ltcg_tax_nominal"),
        "niit_nominal":                          r("niit_nominal"),
        "state_tax_nominal":                     r("state_tax_nominal"),
        "medicare_nominal":                      r("medicare_nominal"),
        "aca_nominal":                           r("aca_nominal"),
        "debt_payments_nominal":                 r("debt_payments_nominal"),
        "final_bequest_nominal":                 r("final_bequest_nominal"),
        "final_bequest_today_dollars":           r("final_bequest_today"),
        "heirs_tax_liability_nominal":           r("heirs_tax_liability_nominal"),
        "remaining_debt_balance":                r("remaining_debt_balance"),
        "time_horizon_years":                    int(m["time_horizon_years"]),
        "cumulative_inflation_factor":           round(m["inflation_factor"], 4),
    }


def plan_to_dict(plan) -> dict:
    """
    Serialize a solved Plan to a plain Python dict.

    Raises ValueError if the plan is not solved.
    """
    if plan.caseStatus != "solved":
        raise ValueError(f"Plan is not solved (status: {plan.caseStatus})")

    N = plan.N_n

    # ---- summary (via shared plan_metrics) ------------------------------
    m = plan_metrics(plan)
    summary = _metrics_to_summary(m)

    # ---- per-year arrays ------------------------------------------------
    spending = plan.g_n[:N]
    fed_tax = plan.T_n[:N]
    ltcg_tax = plan.U_n[:N]
    niit = plan.J_n[:N]
    state_tax = plan.st_T_n[:N]
    medicare = plan.m_n[:N] + plan.M_n[:N]
    aca = plan.aca_costs_n[:N]
    roth_conv = np.sum(plan.x_in[:, :N], axis=0)
    ss_income = plan.zetaBar_in[:, :N]
    portfolio_total = np.sum(plan.b_ijn[:, :, :N], axis=(0, 1))

    by_year = []
    for n in range(N):
        year = int(plan.year_n[n])
        by_year.append({
            "year": year,
            "ages": [int(year - int(plan.yobs[i])) for i in range(plan.N_i)],
            "spending": _round(spending[n]),
            "federal_income_tax": _round(fed_tax[n]),
            "ltcg_tax": _round(ltcg_tax[n]),
            "niit": _round(niit[n]),
            "state_tax": _round(state_tax[n]),
            "medicare_premiums": _round(medicare[n]),
            "aca_premiums": _round(aca[n]),
            "roth_conversions": _round(roth_conv[n]),
            "ss_income": [_round(ss_income[i, n]) for i in range(plan.N_i)],
            "portfolio_total": _round(portfolio_total[n]),
        })

    # ---- top-level document ---------------------------------------------
    return {
        "status": plan.caseStatus,
        "case_name": plan._name,
        "objective": plan.objective,
        "individuals": list(plan.inames),
        "start_year": int(plan.year_n[0]),
        "end_year": int(plan.year_n[-1]),
        "time_horizon_years": N,
        "spending_year1_nominal": _round(spending[0]),
        "total_bequest_nominal": summary["final_bequest_nominal"],
        "total_bequest_today_dollars": summary["final_bequest_today_dollars"],
        "summary": summary,
        "by_year": by_year,
    }


def plan_to_json(plan, indent: int = 2) -> str:
    """Return plan_to_dict serialized as a JSON string."""
    return json.dumps(plan_to_dict(plan), indent=indent, cls=_NumpyEncoder)
