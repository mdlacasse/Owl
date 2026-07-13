"""
Turn a solved plan's shadow prices and primal solution into a structured explanation.

Consumes plan._dual_data (populated by solving with options={"withDuals": True})
plus the plan's primal arrays, and produces a JSON-ready dict answering the
questions users actually ask: what to do this year, what is binding, what would
relaxing each goal or rule be worth, why convert this much to Roth, and how full
are the tax brackets.

The explanation leads with a "this_year" section: only first-year decisions are
executed; later years are projections under current tax law and the assumed
return path, re-optimized when the plan is solved again next year.

Explainers are registry-driven.  CONSTRAINT_FAMILIES classifies every constraint
tag family emitted by plan.py; policy-class families surface to the user, either
through a dedicated handler registered with @_shadow_explainer or through the
generic binding-row explainer.  Adding a new constraint family to the LP requires
one CONSTRAINT_FAMILIES entry (and optionally one handler) — nothing else.

Sign conventions: HiGHS row duals are d(minimized objective)/d(rhs).  Multiplying
by _dual_data["objFac"] converts to reported-objective units (today's-dollar
lifetime profile-weighted spending for maxSpending; today's-dollar final bequest
for maxBequest).  Rows written in year-n nominal dollars are further multiplied
by gamma_n[n] to express sensitivities per today's dollar.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import numpy as np

from .. import tax_federal as tx

_TOL = 1e-9  # dual significance
_BIND_TOL = 1.0  # $ slack below which a constraint counts as binding

# Classification of every constraint-row tag family emitted by plan.py, keyed by tag[0].
# Must stay in sync with the tag= arguments passed to addRow/addNewRow there.
#   policy:     user goals and legal rules; binding rows are reported to the user.
#   structural: accounting identities and definitions; always (or trivially) binding,
#               their duals are valuation data used case-by-case in shadow-price handlers.
#   artifact:   big-M links, AMO/SOS1 selectors, convexification and Benders machinery;
#               never shown to the user.
# Policy families without a dedicated handler declare "indices" (names for tag[1:])
# and a "note"; the generic explainer reports their binding rows and relaxation values.
CONSTRAINT_FAMILIES = {
    # policy
    "rmd": {
        "class": "policy",
        "label": "required minimum distribution floor",
        "indices": ("person", "year"),
    },
    "bequest_floor": {
        "class": "policy",
        "label": "minimum final bequest requirement",
        "indices": (),
    },
    "profile_lo": {
        "class": "policy",
        "label": "spending-profile band, lower edge",
        "indices": ("year",),
    },
    "profile_hi": {
        "class": "policy",
        "label": "spending-profile band, upper edge",
        "indices": ("year",),
    },
    "roth_maturation": {
        "class": "policy",
        "label": "Roth 5-year seasoning floor on withdrawals",
        "indices": ("person", "year"),
        "note": "Years where the Roth 5-year rule blocks withdrawals the optimizer would otherwise "
        "make; the value is the objective gain per today's-$ of Roth made available sooner.",
    },
    "hsa_medical_cap": {
        "class": "policy",
        "label": "HSA withdrawals capped by qualified medical expenses",
        "indices": ("year",),
        "note": "Years where tax-free HSA spending is limited by qualified medical expenses; the "
        "value is the objective gain per today's-$ of additional qualified expenses.",
    },
    "state_ret_exempt_cap": {
        "class": "policy",
        "label": "state retirement-income exemption capped by IRA withdrawals",
        "indices": ("year",),
        "note": "Years where the state retirement-income exemption is limited by actual IRA "
        "withdrawals; the value is the gain per today's-$ of additional exemptible income.",
    },
    "ltcg_room20": {
        "class": "policy",
        "label": "room left below the 20% capital-gains bracket",
        "indices": ("year",),
        "note": "Years where realized gains fill the 0%/15% capital-gains brackets completely; "
        "the value is the gain per today's-$ of additional sub-20% bracket room.",
    },
    # structural
    "cash_flow": {"class": "structural", "label": "yearly net cash-flow balance"},
    "taxable_income": {"class": "structural", "label": "yearly federal taxable-income identity"},
    "state_taxable_income": {"class": "structural", "label": "yearly state taxable-income identity"},
    "account_carryover": {"class": "structural", "label": "account balance carryover dynamics"},
    "withdrawal_limit": {"class": "structural", "label": "withdrawals limited to account balance"},
    "surplus_deposit": {"class": "structural", "label": "surplus-to-deposit split between spouses"},
    "ss_age_benefit": {"class": "structural", "label": "SS benefit implied by claiming-age choice"},
    "ltcg_gn_def": {"class": "structural", "label": "ordinary taxable income definition (MILP mode)"},
    "ltcg_partition_lo": {"class": "structural", "label": "capital gains partitioned across LTCG brackets"},
    "niit_magi_def": {"class": "structural", "label": "NIIT MAGI definition"},
    "irmaa_magi_def": {"class": "structural", "label": "Medicare IRMAA MAGI definition"},
    "irmaa_cost_def": {"class": "structural", "label": "Medicare premium implied by IRMAA bracket"},
    "aca_magi_def": {"class": "structural", "label": "ACA MAGI definition"},
    "aca_cost_def": {"class": "structural", "label": "ACA premium implied by subsidy bracket"},
    # artifacts
    "wdorder_txdef_gate": {"class": "artifact", "label": "withdrawal-order big-M gate"},
    "wdorder_roth_gate": {"class": "artifact", "label": "withdrawal-order big-M gate"},
    "wdorder_taxable_exhausted": {"class": "artifact", "label": "withdrawal-order exhaustion link"},
    "wdorder_txdef_exhausted": {"class": "artifact", "label": "withdrawal-order exhaustion link"},
    "wdorder_gate_monotone": {"class": "artifact", "label": "withdrawal-order gate ordering"},
    "amo_surplus_wdraw": {"class": "artifact", "label": "surplus/withdrawal exclusion big-M"},
    "amo_surplus_gate": {"class": "artifact", "label": "surplus/withdrawal exclusion big-M"},
    "amo_surplus_excl": {"class": "artifact", "label": "surplus/withdrawal at-most-one"},
    "amo_roth_conv": {"class": "artifact", "label": "conversion/withdrawal exclusion big-M"},
    "amo_roth_wdraw": {"class": "artifact", "label": "conversion/withdrawal exclusion big-M"},
    "amo_roth_excl": {"class": "artifact", "label": "conversion/withdrawal at-most-one"},
    "ss_tax_plo": {"class": "artifact", "label": "SS-taxability convexification"},
    "ss_tax_phi": {"class": "artifact", "label": "SS-taxability convexification"},
    "ss_tax_pmin_ub": {"class": "artifact", "label": "SS-taxability min() linearization"},
    "ss_tax_pmin_lb_cap": {"class": "artifact", "label": "SS-taxability min() big-M"},
    "ss_tax_pmin_lb_plo": {"class": "artifact", "label": "SS-taxability min() big-M"},
    "ss_tax_tss_ub": {"class": "artifact", "label": "SS-taxability min() linearization"},
    "ss_tax_tss_lb_cap": {"class": "artifact", "label": "SS-taxability min() big-M"},
    "ss_tax_tss_lb_formula": {"class": "artifact", "label": "SS-taxability min() big-M"},
    "ss_age_amo": {"class": "artifact", "label": "SS claiming-month exactly-one selector"},
    "ltcg_zl15_link": {"class": "artifact", "label": "LTCG bracket-regime big-M link"},
    "ltcg_zl20_link": {"class": "artifact", "label": "LTCG bracket-regime big-M link"},
    "ltcg_room15_mip": {"class": "artifact", "label": "LTCG 0% room big-M (MILP mode)"},
    "ltcg_q0_zero": {"class": "artifact", "label": "LTCG 0% shutoff big-M (MILP mode)"},
    "ltcg_room20_mip": {"class": "artifact", "label": "LTCG 15% room big-M (MILP mode)"},
    "ltcg_q01_zero": {"class": "artifact", "label": "LTCG 15% shutoff big-M (MILP mode)"},
    "ltcg_zl_monotone": {"class": "artifact", "label": "LTCG regime-binary ordering"},
    "ltcg_partition_hi": {"class": "artifact", "label": "LTCG partition anti-degeneracy bound"},
    "niit_floor": {"class": "artifact", "label": "NIIT floor big-M"},
    "niit_j_zero": {"class": "artifact", "label": "NIIT shutoff big-M"},
    "niit_magi_cap": {"class": "artifact", "label": "NIIT MAGI-threshold big-M"},
    "niit_surplus_cap": {"class": "artifact", "label": "NIIT surplus cap big-M"},
    "irmaa_amo": {"class": "artifact", "label": "IRMAA bracket exactly-one selector"},
    "irmaa_bracket_lb": {"class": "artifact", "label": "IRMAA bracket bound big-M"},
    "irmaa_bracket_ub": {"class": "artifact", "label": "IRMAA bracket bound big-M"},
    "aca_amo": {"class": "artifact", "label": "ACA bracket exactly-one selector"},
    "aca_bracket_lb": {"class": "artifact", "label": "ACA bracket bound big-M"},
    "aca_bracket_ub": {"class": "artifact", "label": "ACA bracket bound big-M"},
    "benders_cut": {"class": "artifact", "label": "Benders optimality cut"},
}


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
        "this_year": _this_year(plan, dd),
        "shadow_prices": _shadow_prices(plan, dd),
        "binding_constraints": _binding_constraints(plan, dd),
        "roth_conversions": _roth_analysis(plan, dd),
        "tax_brackets": _bracket_analysis(plan),
        "account_depletion": _depletion(plan),
        "caveats": [
            "Only the first year's decisions are executed. Later years are projections under "
            "current tax law and the assumed return path; they will change when the plan is "
            "re-solved next year, so present them as trajectory context, not recommendations.",
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


# ─────────────────────────────────────────────────────────────────────────────
# This-year section: the executed decisions (year n=0), reported first.
# ─────────────────────────────────────────────────────────────────────────────


def _year0_bracket(plan):
    """Top ordinary-income bracket reached in year 0 and the room left in it."""
    f = plan.f_tn
    filled = [t for t in range(f.shape[0]) if f[t, 0] > 1.0]
    if not filled:
        return None
    t_top = max(filled)
    headroom = (plan.DeltaBar_tn[t_top, 0] - f[t_top, 0]) / plan.gamma_n[0]
    return {
        "top_bracket_rate_pct": _round(plan.theta_tn[t_top, 0] * 100, 1),
        "headroom_in_bracket": _round(max(headroom, 0.0)),
        "filled_to_boundary": bool(headroom < 1.0),
    }


def _year0_thresholds(plan):
    """Proximity to the tax cliffs this year's income can trigger (primal headroom,
    not duals: marginal prices are the wrong tool for discrete threshold effects)."""
    thisyear = int(plan.year_n[0])
    magi0 = float(plan.MAGI_n[0])
    couple0 = plan.N_i == 2 and plan.n_d > 0
    prox = {}

    # NIIT threshold (statutory, not inflation-indexed).
    T_niit = 250_000.0 if couple0 else 200_000.0
    prox["niit"] = {
        "magi": _round(magi0),
        "threshold": T_niit,
        "headroom": _round(T_niit - magi0),
        "subject": bool(magi0 > T_niit),
    }

    # IRMAA: this year's MAGI sets Medicare premiums two years from now.
    n_prem = 2
    if plan.N_n > n_prem:
        on_medicare = [
            i
            for i in range(plan.N_i)
            if thisyear + n_prem - plan.yobs[i] >= 65 and n_prem < plan.horizons[i]
        ]
        if on_medicare:
            status = 1 if (plan.N_i == 2 and plan.n_d > n_prem) else 0
            thresholds = plan.gamma_n[n_prem] * tx.irmaaBrackets[status][1:]
            tier = int(np.sum(magi0 > thresholds))
            entry = {
                "affects_premium_year": thisyear + n_prem,
                "current_tier": tier,
                "note": "Two-year lookback: this year's MAGI determines IRMAA surcharges in "
                f"{thisyear + n_prem}.",
            }
            if tier < len(thresholds):
                entry["headroom_to_next_tier"] = _round(float(thresholds[tier]) - magi0)
            prox["irmaa"] = entry

    # ACA: current-year MAGI drives this year's subsidy when pre-Medicare years exist.
    if getattr(plan, "n_aca", 0) > 0:
        prox["aca"] = {
            "net_premium_this_year": _round(float(plan.ACA_n[0])),
            "aca_years_remaining": int(plan.n_aca),
            "note": "ACA subsidies depend on current-year MAGI; extra income this year raises "
            "this year's premium.",
        }

    # SS taxability tier actually reached this year.
    if float(np.sum(plan.zetaBar_in[:, 0])) > 0:
        prox["social_security"] = {"taxable_fraction_pct": _round(float(plan.Psi_n[0]) * 100, 1)}

    return prox


def _this_year(plan, dd):
    """The first plan year's decisions — the only ones that are executed."""
    thisyear = int(plan.year_n[0])
    g0 = plan.gamma_n[0]
    people = []
    for i in range(plan.N_i):
        w = plan.w_ijn[i, :, 0] / g0
        person = {
            "person": plan.inames[i],
            "age": thisyear - int(plan.yobs[i]),
            "roth_conversion": _round(plan.x_in[i, 0] / g0),
            "withdrawals": {
                "taxable": _round(w[0]),
                "tax_deferred": _round(w[1]),
                "roth": _round(w[2]),
                "hsa": _round(w[3]) if w.shape[0] > 3 else 0.0,
            },
            "rmd_required": _round(plan.rho_in[i, 0] * plan.b_ijn[i, 1, 0] / g0),
        }
        people.append(person)

    out = {
        "year": thisyear,
        "actions": {
            "per_person": people,
            "net_spending": _round(float(plan.g_n[0]) / g0),
            "surplus_deposit": _round(float(plan.s_n[0]) / g0),
        },
    }

    bracket = _year0_bracket(plan)
    if bracket:
        out["tax_bracket"] = bracket

    thresholds = _year0_thresholds(plan)
    if thresholds:
        out["threshold_proximity"] = thresholds

    # Marginal value of a dollar this year (year-0 cash-flow dual) and, when the
    # year-0 conversion cap binds, what one more dollar of cap would be worth.
    marginal = {}
    for t, i in _tagged_rows(dd, "cash_flow"):
        if t[1] == 0:
            marginal["value_of_extra_dollar_now"] = _round(dd["row_dual"][i] * dd["objFac"] * g0, 4)
            break
    if "x" in plan.vm:
        for i in range(plan.N_i):
            j = plan.vm["x"].idx(i, 0)
            cap = dd["col_ub"][j]
            if np.isfinite(cap) and cap > 0 and abs(plan.x_in[i, 0] - cap) < _BIND_TOL:
                # d(reported objective)/d(column ub) = col_dual * objFac, always >= 0.
                marginal["value_per_dollar_of_extra_conversion_cap"] = _round(
                    dd["col_dual"][j] * dd["objFac"] * g0, 4
                )
    if marginal:
        out["marginal_values"] = marginal

    out["note"] = (
        "These are the decisions to execute now. Everything past this year is a projection "
        "that assumes today's tax law and the modeled returns; re-solve the plan yearly."
    )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Shadow-price explainers: registry of dedicated handlers plus a generic
# binding-row explainer for policy families without one.
# ─────────────────────────────────────────────────────────────────────────────

_SHADOW_EXPLAINERS = []  # (output key, handled families, handler(plan, dd) -> payload|None)


def _shadow_explainer(key, families=()):
    def register(fn):
        _SHADOW_EXPLAINERS.append((key, tuple(families), fn))
        return fn

    return register


def _shadow_prices(plan, dd):
    sp = {}
    handled = set()
    for key, families, handler in _SHADOW_EXPLAINERS:
        handled.update(families)
        payload = handler(plan, dd)
        if payload:
            sp[key] = payload
    for family, spec in CONSTRAINT_FAMILIES.items():
        if spec["class"] != "policy" or family in handled:
            continue
        payload = _generic_binding_rows(plan, dd, family, spec)
        if payload:
            sp[family] = payload
    return sp


def _generic_binding_rows(plan, dd, family, spec):
    """Report binding rows of a one-sided policy family and their relaxation values.

    For a row binding at its upper bound, raising the bound by one nominal dollar
    changes the reported objective by dual*objFac; at a lower bound, lowering it
    changes the objective by -dual*objFac.  Both are converted to today's dollars.
    """
    dual = dd["row_dual"]
    rows = []
    for t, i in _tagged_rows(dd, family):
        if abs(dual[i]) <= _TOL:
            continue
        lb_finite = bool(np.isfinite(dd["row_lb"][i]))
        ub_finite = bool(np.isfinite(dd["row_ub"][i]))
        if lb_finite == ub_finite:
            continue  # equality or range row: no single relaxation direction
        sign = 1.0 if ub_finite else -1.0
        entry = {}
        n = None
        for name, val in zip(spec.get("indices", ()), t[1:], strict=False):
            if name == "year":
                n = int(val)
                entry["year"] = int(plan.year_n[n])
            elif name == "person":
                entry["person"] = plan.inames[int(val)]
            else:
                entry[name] = int(val)
        gamma = plan.gamma_n[n] if n is not None else 1.0
        entry["gain_per_dollar_of_relaxation_today"] = _round(sign * dual[i] * dd["objFac"] * gamma, 4)
        rows.append(entry)
    if not rows:
        return None
    payload = {"binding_rows": rows}
    payload["note"] = spec.get("note", spec["label"])
    return payload


@_shadow_explainer("bequest_floor", families=("bequest_floor",))
def _explain_bequest_floor(plan, dd):
    # Bequest floor (maxSpending): cost of each extra today's-$ the estate must retain.
    for _t, i in _tagged_rows(dd, "bequest_floor"):
        sens = dd["row_dual"][i] * dd["objFac"] * plan.gamma_n[plan.N_n]  # rhs in nominal year-N dollars
        if abs(sens) > _TOL:
            return {
                "lifetime_spending_cost_per_dollar_of_bequest_today": _round(-sens, 4),
                "note": "Cost, in lifetime spending (today's $), of requiring one more today's-$ "
                "of final bequest. Below 1.0 because reserved money keeps growing.",
            }
    return None


@_shadow_explainer("spending_floor")
def _explain_spending_floor(plan, dd):
    # Spending floor (maxBequest / fixedSpending): g(0) is a fixed variable; its reduced
    # cost is the marginal bequest cost of each extra dollar of required year-1 spending.
    if plan.objective != "maxBequest" or "g" not in plan.vm:
        return None
    j = plan.vm["g"].idx(0)
    sens = dd["col_dual"][j] * dd["objFac"]  # year-0 nominal ~ today's $
    if abs(sens) <= _TOL:
        return None
    return {
        "bequest_cost_per_dollar_of_year1_spending": _round(-sens, 4),
        "note": "Final bequest (today's $) given up per extra dollar of required "
        "first-year net spending.",
    }


@_shadow_explainer("value_of_extra_income_by_year", families=("cash_flow",))
def _explain_cash_flow(plan, dd):
    # Cash-flow duals: the plan's endogenous discount curve — value of one extra
    # today's-$ of external income arriving in year n.
    cf = [(t[1], dd["row_dual"][i]) for t, i in _tagged_rows(dd, "cash_flow")]
    if not cf:
        return None
    cf.sort()
    vals = [_round(d * dd["objFac"] * plan.gamma_n[n], 4) for n, d in cf]
    yrs = [int(plan.year_n[n]) for n, _ in cf]
    top = sorted(zip(yrs, vals, strict=True), key=lambda p: -p[1])[:3]
    return {
        "years": yrs,
        "value_per_today_dollar": vals,
        "most_valuable_years": [{"year": y, "value": v} for y, v in top],
        "note": "Marginal lifetime-objective value of one extra today's-$ of income in each "
        "year. Peaks mark the cash-constrained years; the shape is the plan's own "
        "discount curve.",
    }


@_shadow_explainer("rmd_floors", families=("rmd",))
def _explain_rmd(plan, dd):
    # RMD floors: spending gained per dollar of RMD requirement waived, by year.
    rmd = []
    for t, i in _tagged_rows(dd, "rmd"):
        _, person, n = t
        sens = -dd["row_dual"][i] * dd["objFac"] * plan.gamma_n[n]
        if abs(sens) > _TOL:
            rmd.append(
                {
                    "person": plan.inames[person],
                    "year": int(plan.year_n[n]),
                    "spending_gain_per_dollar_less_rmd_today": _round(sens, 4),
                }
            )
    if not rmd:
        return None
    return {
        "binding_years": rmd,
        "note": "Years where required minimum distributions force withdrawals the optimizer "
        "would not otherwise make, and the marginal cost of each forced dollar.",
    }


@_shadow_explainer("spending_profile_band", families=("profile_lo", "profile_hi"))
def _explain_profile_band(plan, dd):
    # Spending-profile band: years pinned against the +/- slack band around the profile.
    # With spendingSlack=0 the band is an equality and every year is trivially pinned —
    # only report when a real band exists.
    if getattr(plan, "lambdha", 0) <= 0:
        return None
    dual = dd["row_dual"]
    lo = [int(plan.year_n[t[1]]) for t, i in _tagged_rows(dd, "profile_lo") if abs(dual[i]) > _TOL]
    hi = [int(plan.year_n[t[1]]) for t, i in _tagged_rows(dd, "profile_hi") if abs(dual[i]) > _TOL]
    if not (lo or hi):
        return None
    return {
        "pinned_at_lower_edge": lo,
        "pinned_at_upper_edge": hi,
        "note": "Years where spending sits at the edge of the allowed +/-slack band around "
        "the profile shape; widening spendingSlack would let the optimizer shift "
        "spending further across these years.",
    }


def _binding_constraints(plan, dd):
    """Compact list of policy-class tagged rows that are active with a significant dual.

    Structural rows (identities, always binding) and formulation artifacts (big-M,
    AMO/SOS1, convexification) are filtered out via CONSTRAINT_FAMILIES; unknown
    families are kept so a newly tagged constraint surfaces rather than vanishes.
    """
    act, lb, ub, dual = dd["row_activity"], dd["row_lb"], dd["row_ub"], dd["row_dual"]
    profile_is_band = getattr(plan, "lambdha", 0) > 0
    out = []
    for i, t in enumerate(dd["row_tags"]):
        if t is None or abs(dual[i]) <= _TOL:
            continue
        spec = CONSTRAINT_FAMILIES.get(t[0], {"class": "policy"})
        if spec["class"] != "policy":
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
        if side:
            label = t[0] if len(t) == 1 else f"{t[0]}[{','.join(str(v) for v in t[1:])}]"
            entry = {"constraint": label, "side": side}
            if "label" in spec:
                entry["description"] = spec["label"]
            out.append(entry)
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
                # d(reported objective)/d(column ub) = col_dual * objFac, always >= 0
                # (relaxing an upper bound cannot hurt the LP objective).
                sens = dd["col_dual"][j] * objFac * gamma[n]
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
