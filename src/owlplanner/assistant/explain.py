"""
Turn a solved plan's shadow prices and primal solution into a structured explanation.

Consumes plan._dual_data (populated by solving with options={"withDuals": True})
plus the plan's primal arrays, and produces a JSON-ready dict answering the
questions users actually ask: what is binding, what would relaxing each goal or
rule be worth, why convert this much to Roth, and how full are the tax brackets.

Sign conventions: HiGHS row duals are d(minimized objective)/d(rhs).  Multiplying
by _dual_data["objFac"] converts to reported-objective units (today's-dollar
lifetime profile-weighted spending for maxSpending; today's-dollar final bequest
for maxBequest).  Rows written in year-n nominal dollars are further multiplied
by gamma_n[n] to express sensitivities per today's dollar.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import numpy as np

_TOL = 1e-9  # dual significance
_BIND_TOL = 1.0  # $ slack below which a constraint counts as binding


def _round(v, digits=2):
    return float(np.round(float(v), digits))


def build_explanation(plan) -> dict:
    """Build the explanation dict from a solved plan. Requires withDuals=True at solve."""
    if getattr(plan, "caseStatus", None) != "solved":
        return {"error": f"Plan is not solved (status: {getattr(plan, 'caseStatus', 'unknown')})."}
    dd = getattr(plan, "_dual_data", None)
    if dd is None:
        return {"error": "No dual data on this plan. Solve with options={'withDuals': True} first."}

    out = {
        "objective": plan.objective,
        "sensitivity_units": (
            "today's dollars of total lifetime (profile-weighted) net spending"
            if plan.objective == "maxSpending"
            else "today's dollars of final after-tax bequest"
        ),
        "shadow_prices": _shadow_prices(plan, dd),
        "binding_constraints": _binding_constraints(plan, dd),
        "roth_conversions": _roth_analysis(plan, dd),
        "tax_brackets": _bracket_analysis(plan),
        "account_depletion": _depletion(plan),
        "caveats": [
            "Shadow prices are marginal (valid for small changes) and hold the discrete choices "
            "(tax/IRMAA/ACA bracket selections, Roth-exclusion binaries) and self-consistent "
            "quantities (SS taxability, IRMAA premiums) fixed at their solved values.",
            "Large parameter changes can switch brackets or binaries; re-solve to evaluate them.",
        ],
    }
    return out


def _tagged_rows(dd, family):
    """Yield (tag, row_index) for rows whose tag starts with *family*."""
    for i, t in enumerate(dd["row_tags"]):
        if t is not None and t[0] == family:
            yield t, i


def _shadow_prices(plan, dd):
    objFac = dd["objFac"]
    dual = dd["row_dual"]
    gamma = plan.gamma_n
    years = plan.year_n
    sp = {}

    # Bequest floor (maxSpending): cost of each extra today's-$ the estate must retain.
    for t, i in _tagged_rows(dd, "bequest_floor"):
        sens = dual[i] * objFac * gamma[plan.N_n]  # row rhs is in nominal year-N dollars
        if abs(sens) > _TOL:
            sp["bequest_floor"] = {
                "lifetime_spending_cost_per_dollar_of_bequest_today": _round(-sens, 4),
                "note": "Cost, in lifetime spending (today's $), of requiring one more today's-$ "
                "of final bequest. Below 1.0 because reserved money keeps growing.",
            }

    # Spending floor (maxBequest / fixedSpending): g(0) is a fixed variable; its reduced
    # cost is the marginal bequest cost of each extra dollar of required year-1 spending.
    if plan.objective == "maxBequest" and "g" in plan.vm:
        j = plan.vm["g"].idx(0)
        sens = dd["col_dual"][j] * objFac  # year-0 nominal ~ today's $
        if abs(sens) > _TOL:
            sp["spending_floor"] = {
                "bequest_cost_per_dollar_of_year1_spending": _round(-sens, 4),
                "note": "Final bequest (today's $) given up per extra dollar of required "
                "first-year net spending.",
            }

    # Cash-flow duals: the plan's endogenous discount curve — value of one extra
    # today's-$ of external income arriving in year n.
    cf = [(t[1], dual[i]) for t, i in _tagged_rows(dd, "cash_flow")]
    if cf:
        cf.sort()
        vals = [_round(d * objFac * gamma[n], 4) for n, d in cf]
        yrs = [int(years[n]) for n, _ in cf]
        top = sorted(zip(yrs, vals), key=lambda p: -p[1])[:3]
        sp["value_of_extra_income_by_year"] = {
            "years": yrs,
            "value_per_today_dollar": vals,
            "most_valuable_years": [{"year": y, "value": v} for y, v in top],
            "note": "Marginal lifetime-objective value of one extra today's-$ of income in each "
            "year. Peaks mark the cash-constrained years; the shape is the plan's own "
            "discount curve.",
        }

    # RMD floors: spending gained per dollar of RMD requirement waived, by year.
    rmd = []
    for t, i in _tagged_rows(dd, "rmd"):
        _, person, n = t
        sens = -dual[i] * objFac * gamma[n]
        if abs(sens) > _TOL:
            rmd.append(
                {
                    "person": plan.inames[person],
                    "year": int(years[n]),
                    "spending_gain_per_dollar_less_rmd_today": _round(sens, 4),
                }
            )
    if rmd:
        sp["rmd_floors"] = {
            "binding_years": rmd,
            "note": "Years where required minimum distributions force withdrawals the optimizer "
            "would not otherwise make, and the marginal cost of each forced dollar.",
        }

    # Spending-profile band: years pinned against the +/- slack band around the profile.
    # With spendingSlack=0 the band is an equality and every year is trivially pinned —
    # only report when a real band exists.
    lo, hi = [], []
    if getattr(plan, "lambdha", 0) > 0:
        lo = [int(years[t[1]]) for t, i in _tagged_rows(dd, "profile_lo") if abs(dual[i]) > _TOL]
        hi = [int(years[t[1]]) for t, i in _tagged_rows(dd, "profile_hi") if abs(dual[i]) > _TOL]
    if lo or hi:
        sp["spending_profile_band"] = {
            "pinned_at_lower_edge": lo,
            "pinned_at_upper_edge": hi,
            "note": "Years where spending sits at the edge of the allowed +/-slack band around "
            "the profile shape; widening spendingSlack would let the optimizer shift "
            "spending further across these years.",
        }
    return sp


def _binding_constraints(plan, dd):
    """Compact list of tagged rows that are active with a significant dual."""
    act, lb, ub, dual = dd["row_activity"], dd["row_lb"], dd["row_ub"], dd["row_dual"]
    profile_is_band = getattr(plan, "lambdha", 0) > 0
    out = []
    for i, t in enumerate(dd["row_tags"]):
        if t is None or abs(dual[i]) <= _TOL:
            continue
        if t[0] in ("profile_lo", "profile_hi") and not profile_is_band:
            continue  # zero-slack profile rows are equalities; always active, not informative
        side = None
        if np.isfinite(lb[i]) and abs(act[i] - lb[i]) < _BIND_TOL:
            side = "lower"
        if np.isfinite(ub[i]) and abs(act[i] - ub[i]) < _BIND_TOL:
            side = "upper" if side is None else "equality"
        if lb[i] == ub[i]:
            side = "equality"
        if side and t[0] != "cash_flow":  # equalities are always 'binding'; cash flow reported above
            label = t[0] if len(t) == 1 else f"{t[0]}[{','.join(str(v) for v in t[1:])}]"
            out.append({"constraint": label, "side": side})
    return out


def _roth_analysis(plan, dd):
    """Conversion schedule plus binding-cap detection from column bounds and reduced costs."""
    objFac = dd["objFac"]
    gamma = plan.gamma_n
    years = plan.year_n
    schedule = []
    binding = []
    for i in range(plan.N_i):
        for n in range(plan.N_n):
            amt = float(plan.x_in[i, n])
            if amt < 1.0:
                continue
            entry = {
                "person": plan.inames[i],
                "year": int(years[n]),
                "amount_today": _round(amt / gamma[n]),
            }
            schedule.append(entry)
            j = plan.vm["x"].idx(i, n)
            cap = dd["col_ub"][j]
            if np.isfinite(cap) and cap > 0 and abs(amt - cap) < _BIND_TOL:
                sens = -dd["col_dual"][j] * objFac * gamma[n]
                binding.append(
                    {
                        "person": plan.inames[i],
                        "year": int(years[n]),
                        "value_per_dollar_of_extra_cap_today": _round(sens, 4),
                    }
                )
    result = {
        "schedule_today_dollars": schedule,
        "total_converted_today": _round(sum(e["amount_today"] for e in schedule)),
    }
    if binding:
        result["cap_binding_years"] = binding
        result["note"] = "Years where the conversion cap is binding; the value shows what one more "
        result["note"] += "dollar of allowed conversion would add to the objective."
    return result


def _bracket_analysis(plan):
    """Per-year federal ordinary-income bracket fill from the f_tn variables."""
    f = plan.f_tn
    width = plan.DeltaBar_tn
    rates = plan.theta_tn
    gamma = plan.gamma_n
    years = plan.year_n
    rows = []
    for n in range(plan.N_n):
        filled = [t for t in range(f.shape[0]) if f[t, n] > 1.0]
        if not filled:
            continue
        t_top = max(filled)
        headroom = (width[t_top, n] - f[t_top, n]) / gamma[n]
        rows.append(
            {
                "year": int(years[n]),
                "top_bracket_rate_pct": _round(rates[t_top, n] * 100, 1),
                "headroom_in_bracket_today": _round(max(headroom, 0.0)),
                "filled_to_boundary": bool(headroom < 1.0),
            }
        )
    return {
        "by_year": rows,
        "note": "Top federal ordinary-income bracket reached each year and the room left in it "
        "(today's $). filled_to_boundary years are where the optimizer deliberately fills "
        "the bracket — typically with Roth conversions — and stops at the edge.",
    }


def _depletion(plan):
    """First year each account type is (effectively) emptied, per person."""
    jnames = ("taxable", "tax_deferred", "roth", "hsa")
    years = plan.year_n
    out = []
    b = plan.b_ijn
    for i in range(plan.N_i):
        for j in range(min(plan.N_j, b.shape[1])):
            if b[i, j, 0] < 1.0:
                continue
            below = np.where(b[i, j, : plan.N_n + 1] < 1.0)[0]
            if below.size:
                n_dep = int(below[0])
                yr = int(years[min(n_dep, plan.N_n - 1)]) + (1 if n_dep >= plan.N_n else 0)
                out.append({"person": plan.inames[i], "account": jnames[j], "depleted_in": yr})
    return {
        "events": out,
        "note": "First year each initially-funded account reaches zero; the order reveals the "
        "withdrawal sequencing the optimizer chose.",
    }
