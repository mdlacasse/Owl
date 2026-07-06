"""
Session-aware tools for the embedded AI assistant.

Read-only bridges between the chat and the live Streamlit session: they
serialize the currently open case through the tested ui_to_config path so the
assistant sees exactly what the solver would. Deliberately no mutation of
session state — scenario exploration happens through the stateless solver
tools, and results are handed back via save_case files the user loads through
the normal Create Case flow.

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

import json

import sskeys as kz
import assistant_core as core

_NO_PROPS = {"type": "object", "properties": {}, "additionalProperties": False}

SESSION_TOOL_SCHEMAS = [
    {
        "name": "get_current_case",
        "description": "Return the configuration of the case currently open in the Owl app "
        "(TOML-shaped dict: people, balances, fixed income, rates, solver options, and the "
        "wages-and-contributions table), its solve status, and key results when solved. "
        "Call this first whenever the user refers to their case, plan, or numbers.",
        "input_schema": _NO_PROPS,
    },
    {
        "name": "list_open_cases",
        "description": "List the names of the cases currently open in the Owl app and which "
        "one is active.",
        "input_schema": _NO_PROPS,
    },
    {
        "name": "get_current_case_results",
        "description": "Return the full solved results of the case currently open in the Owl "
        "app — the same summary and year-by-year detail run_case returns, for the exact "
        "solution the app is displaying. Use this instead of re-solving when the user asks "
        "about their already-solved plan (e.g. 'what do I withdraw in 2032?'). Fails if the "
        "case has not been solved yet.",
        "input_schema": _NO_PROPS,
    },
]

_METRIC_KEYS = (
    "spending_basis",
    "spending_year1",
    "total_spending_today",
    "final_bequest_today",
    "roth_conversions_today",
    "federal_income_tax_today",
    "state_tax_today",
    "medicare_today",
    "effective_tax_rate",
)


def _wages_records(dic) -> dict:
    """Nonzero rows of the wages-and-contributions table, per person."""
    out = {}
    for i in range(2):
        df = dic.get(f"timeList{i}")
        if df is None:
            continue
        try:
            value_cols = [c for c in df.columns if c != "year"]
            rows = df.loc[(df[value_cols] != 0).any(axis=1)]
            name = dic.get(f"iname{i}", f"person{i}")
            out[name] = rows.to_dict("records")
        except Exception:
            continue
    return out


def get_current_case() -> str:
    if not kz.has_current_case():
        return json.dumps({"error": "No case is currently open in the app."})
    dic = kz.currentCaseDic()
    result = {"case_name": kz.currentCaseName(), "status": dic.get("caseStatus", "unknown")}
    try:
        from owlplanner.config import ui_to_config

        result["config"] = ui_to_config(dic)
    except Exception as e:
        result["config_error"] = f"Case is incomplete or invalid: {e}"
    wages = _wages_records(dic)
    if wages:
        result["wages_and_contributions_nonzero_rows"] = wages
    plan = dic.get("plan")
    if result["status"] == "solved" and plan is not None:
        try:
            from owlplanner.export import plan_metrics

            m = plan_metrics(plan)
            result["key_metrics"] = {k: round(m[k], 2) for k in _METRIC_KEYS if k in m}
        except Exception:
            pass
    return json.dumps(result, default=str)


def list_open_cases() -> str:
    names = kz.onlyCaseNames()
    current = kz.currentCaseName() if kz.has_current_case() else None
    return json.dumps({"open_cases": names, "active_case": current})


def get_current_case_results() -> str:
    if not kz.has_current_case():
        return json.dumps({"error": "No case is currently open in the app."})
    dic = kz.currentCaseDic()
    plan = dic.get("plan")
    if dic.get("caseStatus") != "solved" or plan is None:
        return json.dumps(
            {
                "error": "The current case has not been solved yet. Ask the user to run it "
                "from the app, or solve a copy yourself with run_from_params."
            }
        )
    from owlplanner.cli.formatters import plan_to_dict, _NumpyEncoder

    result = plan_to_dict(plan)
    result["case_name"] = kz.currentCaseName()
    return json.dumps(result, cls=_NumpyEncoder, default=str)


def all_tool_schemas() -> list[dict]:
    return SESSION_TOOL_SCHEMAS + core.stateless_tool_schemas()


def execute_tool(name: str, args: dict) -> str:
    if name == "get_current_case":
        return get_current_case()
    if name == "list_open_cases":
        return list_open_cases()
    if name == "get_current_case_results":
        return get_current_case_results()
    return core.call_stateless_tool(name, args)
