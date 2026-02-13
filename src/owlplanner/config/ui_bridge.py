"""
Bridge between canonical configuration dict and UI flat session-state dict.

Maps between the nested TOML/config structure and the flat keys used by
Streamlit widgets (getCaseKey, setCaseKey).

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from datetime import date, datetime
from typing import Any

from owlplanner.config.schema import KNOWN_SECTIONS
from owlplanner.rates import FROM

# Account type ordering for UI (txbl, txDef, txFree)
ACC_UI = ["txbl", "txDef", "txFree"]
# Account type ordering for config
ACC_CONF = ["taxable", "tax-deferred", "tax-free"]
ACC_KEY_MAP = {
    "taxable": "taxable_savings_balances",
    "tax-deferred": "tax_deferred_savings_balances",
    "tax-free": "tax_free_savings_balances",
}


def _start_date_to_ui(start_date: str) -> date:
    """Convert config start_date string to UI date object."""
    tdate = start_date.replace("/", "-").split("-")
    if len(tdate) == 2:
        mystart = str(date.today().year) + "-" + start_date
    elif len(tdate) == 3:
        mystart = str(date.today().year) + "-" + tdate[-2] + "-" + tdate[-1]
    else:
        mystart = str(date.today())  # "today"
    return datetime.strptime(mystart, "%Y-%m-%d").date()


def _age_float_to_ym(age: float) -> tuple[int, int]:
    """Convert float age (e.g. 67.5) to (year, month) for UI."""
    return int(age), round((age % 1.0) * 12)


def config_to_ui(diconf: dict) -> dict:
    """
    Convert canonical configuration dict to flat UI session-state style dict.

    Produces the same structure as genDic(plan) but sourced from diconf.
    Does NOT include plan, summaryDf, casetoml, caseStatus, logs, id - those
    are set separately by the caller.
    """
    known = {k: v for k, v in diconf.items() if k in KNOWN_SECTIONS}
    bi = known.get("basic_info", {})
    sa = known.get("savings_assets", {})
    hfp = known.get("household_financial_profile", {})
    fi = known.get("fixed_income", {})
    rs = known.get("rates_selection", {})
    aa = known.get("asset_allocation", {})
    op = known.get("optimization_parameters", {})
    so = known.get("solver_options", {})
    res = known.get("results", {})

    names = bi.get("names", [])
    ni = len(names)
    status = bi.get("status", "single" if ni == 1 else "married")

    dic: dict[str, Any] = {}
    dic["name"] = known.get("case_name", "")
    dic["description"] = known.get("description", "")
    dic["status"] = status

    start_date_str = bi.get("start_date", "today")
    if start_date_str == "today":
        start_date_str = str(date.today())
    dic["startDate"] = _start_date_to_ui(start_date_str)

    dic["interpMethod"] = aa.get("interpolation_method", "s-curve")
    dic["interpCenter"] = float(aa.get("interpolation_center", 15.0))
    dic["interpWidth"] = float(aa.get("interpolation_width", 5.0))
    dic["spendingProfile"] = op.get("spending_profile", "smile")
    if dic["spendingProfile"] == "smile":
        dic["smileDip"] = int(op.get("smile_dip", 15))
        dic["smileIncrease"] = int(op.get("smile_increase", 12))
        dic["smileDelay"] = int(op.get("smile_delay", 0))
    else:
        dic["smileDip"] = 15
        dic["smileIncrease"] = 12
        dic["smileDelay"] = 0

    dic["survivor"] = int(op.get("surviving_spouse_spending_percent", 60))
    dic["divRate"] = float(rs.get("dividend_rate", 1.8))
    dic["heirsTx"] = float(rs.get("heirs_rate_on_tax_deferred_estate", 30.0))
    dic["yOBBBA"] = int(rs.get("obbba_expiration_year", 2032))
    dic["surplusFraction"] = float(sa.get("spousal_surplus_deposit_fraction", 0.5))
    dic["plots"] = res.get("default_plots", "nominal")
    dic["allocType"] = aa.get("type", "individual")
    dic["timeListsFileName"] = hfp.get("HFP_file_name", "None")

    for j in range(3):
        dic[f"benf{j}"] = sa.get("beneficiary_fractions", [1.0, 1.0, 1.0])[j]

    dobs = bi.get("date_of_birth", ["1965-01-15"] * ni)
    life = bi.get("life_expectancy", [89] * ni)
    ss_amt = fi.get("social_security_pia_amounts", [0] * ni)
    ss_ages = fi.get("social_security_ages", [67.0] * ni)
    p_amt = fi.get("pension_monthly_amounts", [0.0] * ni)
    p_ages = fi.get("pension_ages", [65.0] * ni)
    p_idx = fi.get("pension_indexed", [True] * ni)

    for i in range(ni):
        dic[f"iname{i}"] = names[i] if i < len(names) else ""
        dic[f"dob{i}"] = dobs[i] if i < len(dobs) else "1965-01-15"
        dic[f"life{i}"] = life[i] if i < len(life) else 89
        sy, sm = _age_float_to_ym(ss_ages[i] if i < len(ss_ages) else 67.0)
        dic[f"ssAge_y{i}"] = sy
        dic[f"ssAge_m{i}"] = sm
        dic[f"ssAmt{i}"] = ss_amt[i] if i < len(ss_amt) else 0
        py, pm = _age_float_to_ym(p_ages[i] if i < len(p_ages) else 65.0)
        dic[f"pAge_y{i}"] = py
        dic[f"pAge_m{i}"] = pm
        dic[f"pAmt{i}"] = p_amt[i] if i < len(p_amt) else 0.0
        dic[f"pIdx{i}"] = p_idx[i] if i < len(p_idx) else True

        for j, acc in enumerate(ACC_CONF):
            key = ACC_KEY_MAP[acc]
            vals = sa.get(key, [0.0] * ni)
            dic[ACC_UI[j] + str(i)] = vals[i] if i < len(vals) else 0.0  # config $k = UI $k

        alloc_type = aa.get("type", "individual")
        if alloc_type == "individual" or alloc_type == "spouses":
            generic = aa.get("generic", [[[60, 40, 0, 0], [70, 30, 0, 0]]])
            g = generic[i] if i < len(generic) else [[60, 40, 0, 0], [70, 30, 0, 0]]
            for k in range(4):
                dic[f"j3_init%{k}_{i}"] = int(g[0][k])
                dic[f"j3_fin%{k}_{i}"] = int(g[1][k])
        else:
            for j, acc in enumerate(ACC_CONF):
                arr = aa.get(acc, [[[60, 40, 0, 0], [70, 30, 0, 0]]])
                a = arr[i] if i < len(arr) else [[60, 40, 0, 0], [70, 30, 0, 0]]
                for k in range(4):
                    dic[f"j{j}_init%{k}_{i}"] = int(a[0][k])
                    dic[f"j{j}_fin%{k}_{i}"] = int(a[1][k])

    # Solver options
    opt_list = [
        "netSpending", "maxIter", "maxRothConversion", "maxTime", "noRothConversions",
        "startRothConversions", "bequest", "solver", "noLateSurplus",
        "spendingSlack", "oppCostX", "amoConstraints", "amoRoth", "amoSurplus",
        "withSCLoop", "absTol", "bigMirmaa", "bigMamo", "relTol",
    ]
    for key in opt_list:
        if key in so:
            dic[key] = so[key]

    with_med = so.get("withMedicare", "loop")
    dic["computeMedicare"] = with_med != "None"
    dic["optimizeMedicare"] = with_med == "optimize"

    if "previousMAGIs" in so:
        dic["MAGI0"] = so["previousMAGIs"][0]
        dic["MAGI1"] = so["previousMAGIs"][1]

    obj = op.get("objective", "maxSpending")
    dic["objective"] = "Net spending" if obj == "maxSpending" else "Bequest"

    rate_method = rs.get("method", "historical average")
    if rate_method in ["default", "conservative", "optimistic", "historical average", "user"]:
        dic["rateType"] = "fixed"
        dic["fixedType"] = rate_method
    else:
        dic["rateType"] = "varying"
        dic["varyingType"] = rate_method

    values = rs.get("values", [6.0, 4.0, 3.3, 2.8])
    for k in range(4):
        dic[f"fxRate{k}"] = 100 * (values[k] if k < len(values) else 0)

    if rate_method in ["historical average", "histochastic", "historical"]:
        dic["yfrm"] = rs.get("from", 1969)
        dic["yto"] = rs.get("to", date.today().year - 1)
    else:
        dic["yfrm"] = FROM
        dic["yto"] = date.today().year - 1

    if rate_method in ["stochastic", "histochastic"]:
        means = rs.get("values", [6.0, 4.0, 3.3, 2.8])
        stdevs = rs.get("standard_deviations", [17.0, 8.0, 10.0, 3.0])
        corr = rs.get("correlations", [0.4, 0.26, -0.22, 0.84, -0.39, -0.39])
        for k in range(4):
            dic[f"mean{k}"] = 100 * (means[k] if k < len(means) else 0)
            dic[f"stdev{k}"] = 100 * (stdevs[k] if k < len(stdevs) else 0)
        for q in range(1, 7):
            dic[f"corr{q}"] = corr[q - 1] if q - 1 < len(corr) else 0
        dic["reproducibleRates"] = rs.get("reproducible_rates", False)
        dic["rateSeed"] = rs.get("rate_seed")

    dic["reverse_sequence"] = rs.get("reverse_sequence", False)
    dic["roll_sequence"] = rs.get("roll_sequence", 0)

    return dic


def ui_to_config(uidic: dict) -> dict:
    """
    Convert flat UI session-state dict to canonical configuration dict.

    Extracts config-relevant keys from the case dict. Ignores runtime keys
    (plan, summaryDf, casetoml, caseStatus, logs, id, etc.).
    """
    status = uidic.get("status", "single")
    ni = 2 if status == "married" else 1

    names = []
    dobs = []
    life = []
    for i in range(ni):
        n = uidic.get(f"iname{i}", "")
        if n is None:
            n = ""
        names.append(n)
        dobs.append(uidic.get(f"dob{i}", "1965-01-15") or "1965-01-15")
        life.append(int(uidic.get(f"life{i}", 89) or 89))

    start_date = uidic.get("startDate")
    if hasattr(start_date, "strftime"):
        start_date = start_date.strftime("%Y-%m-%d")
    elif start_date is None:
        start_date = "today"

    diconf: dict[str, Any] = {
        "case_name": uidic.get("name", ""),
        "description": uidic.get("description", ""),
        "basic_info": {
            "status": status,
            "names": names,
            "date_of_birth": dobs,
            "life_expectancy": life,
            "start_date": start_date,
        },
        "savings_assets": {},
        "household_financial_profile": {
            "HFP_file_name": uidic.get("timeListsFileName", "None") or "None",
        },
        "fixed_income": {
            "pension_monthly_amounts": [],
            "pension_ages": [],
            "pension_indexed": [],
            "social_security_pia_amounts": [],
            "social_security_ages": [],
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": float(uidic.get("heirsTx", 30) or 30),
            "dividend_rate": float(uidic.get("divRate", 1.8) or 1.8),
            "obbba_expiration_year": int(uidic.get("yOBBBA", 2032) or 2032),
            "method": _ui_rate_method_to_config(uidic),
            "reverse_sequence": bool(uidic.get("reverse_sequence", False)),
            "roll_sequence": int(uidic.get("roll_sequence", 0) or 0),
        },
        "asset_allocation": {
            "interpolation_method": uidic.get("interpMethod", "s-curve"),
            "interpolation_center": float(uidic.get("interpCenter", 15) or 15),
            "interpolation_width": float(uidic.get("interpWidth", 5) or 5),
            "type": uidic.get("allocType", "individual"),
        },
        "optimization_parameters": {
            "spending_profile": uidic.get("spendingProfile", "smile"),
            "surviving_spouse_spending_percent": int(uidic.get("survivor", 60) or 60),
            "objective": "maxSpending" if "spending" in str(uidic.get("objective", "Net spending")) else "maxBequest",
            "smile_dip": int(uidic.get("smileDip", 15) or 15),
            "smile_increase": int(uidic.get("smileIncrease", 12) or 12),
            "smile_delay": int(uidic.get("smileDelay", 0) or 0),
        },
        "solver_options": {},
        "results": {"default_plots": uidic.get("plots", "nominal")},
    }

    # Savings: UI $k = config $k (per doc: tables dollars, UI thousands except fixed income)
    for j, acc in enumerate(ACC_CONF):
        key = ACC_KEY_MAP[acc]
        diconf["savings_assets"][key] = [
            float(uidic.get(ACC_UI[j] + str(i), 0) or 0) for i in range(ni)
        ]
    if ni == 2:
        diconf["savings_assets"]["beneficiary_fractions"] = [
            float(uidic.get(f"benf{j}", 1) or 1) for j in range(3)
        ]
        diconf["savings_assets"]["spousal_surplus_deposit_fraction"] = float(
            uidic.get("surplusFraction", 0.5) or 0.5
        )

    # Fixed income
    for i in range(ni):
        sy = int(uidic.get(f"ssAge_y{i}", 67) or 67)
        sm = int(uidic.get(f"ssAge_m{i}", 0) or 0)
        diconf["fixed_income"]["social_security_ages"].append(sy + sm / 12.0)
        diconf["fixed_income"]["social_security_pia_amounts"].append(
            int(uidic.get(f"ssAmt{i}", 0) or 0)
        )
        py = int(uidic.get(f"pAge_y{i}", 65) or 65)
        pm = int(uidic.get(f"pAge_m{i}", 0) or 0)
        diconf["fixed_income"]["pension_ages"].append(py + pm / 12.0)
        diconf["fixed_income"]["pension_monthly_amounts"].append(
            float(uidic.get(f"pAmt{i}", 0) or 0)
        )
        diconf["fixed_income"]["pension_indexed"].append(
            bool(uidic.get(f"pIdx{i}", True))
        )

    # Rates
    _ui_rates_to_config(diconf, uidic, ni)

    # Asset allocation
    alloc_type = uidic.get("allocType", "individual")
    if alloc_type == "account":
        for j, acc in enumerate(ACC_CONF):
            diconf["asset_allocation"][acc] = []
            for i in range(ni):
                init = [int(uidic.get(f"j{j}_init%{k}_{i}", 0) or 0) for k in range(4)]
                fin = [int(uidic.get(f"j{j}_fin%{k}_{i}", 0) or 0) for k in range(4)]
                diconf["asset_allocation"][acc].append([init, fin])
    else:
        diconf["asset_allocation"]["generic"] = []
        for i in range(ni):
            init = [int(uidic.get(f"j3_init%{k}_{i}", 0) or 0) for k in range(4)]
            fin = [int(uidic.get(f"j3_fin%{k}_{i}", 0) or 0) for k in range(4)]
            diconf["asset_allocation"]["generic"].append([init, fin])

    # Solver options
    opt_list = [
        "netSpending", "maxIter", "maxRothConversion", "maxTime", "noRothConversions",
        "startRothConversions", "bequest", "solver", "noLateSurplus",
        "spendingSlack", "oppCostX", "amoConstraints", "amoRoth", "amoSurplus",
        "withSCLoop", "absTol", "bigMirmaa", "bigMamo", "relTol",
    ]
    for key in opt_list:
        val = uidic.get(key)
        if val is not None:
            diconf["solver_options"][key] = val

    compute_med = uidic.get("computeMedicare", True)
    optimize_med = uidic.get("optimizeMedicare", False)
    diconf["solver_options"]["withMedicare"] = (
        "None" if not compute_med else ("optimize" if optimize_med else "loop")
    )

    magi0 = uidic.get("MAGI0")
    magi1 = uidic.get("MAGI1")
    if magi0 is not None and magi1 is not None and (float(magi0 or 0) > 0 or float(magi1 or 0) > 0):
        diconf["solver_options"]["previousMAGIs"] = [float(magi0 or 0), float(magi1 or 0)]

    return diconf


def _ui_rate_method_to_config(uidic: dict) -> str:
    rate_type = uidic.get("rateType", "fixed")
    if rate_type == "fixed":
        return uidic.get("fixedType", "historical average")
    return uidic.get("varyingType", "histochastic")


def _ui_rates_to_config(diconf: dict, uidic: dict, ni: int) -> None:
    """Populate rates_selection from UI keys."""
    rs = diconf["rates_selection"]
    method = rs["method"]

    if method in ["historical average", "historical", "histochastic"]:
        rs["from"] = int(uidic.get("yfrm", 1969) or 1969)
        rs["to"] = int(uidic.get("yto", date.today().year - 1) or date.today().year - 1)
    elif method in ["user", "stochastic"]:
        rs["values"] = [
            float(uidic.get(f"fxRate{k}", 0) or 0) / 100.0 for k in range(4)
        ]
    if method == "stochastic":
        rs["standard_deviations"] = [
            float(uidic.get(f"stdev{k}", 0) or 0) / 100.0 for k in range(4)
        ]
        corr = []
        for q in range(1, 7):
            corr.append(float(uidic.get(f"corr{q}", 0) or 0))
        rs["correlations"] = corr
    if method in ["stochastic", "histochastic"]:
        rs["reproducible_rates"] = bool(uidic.get("reproducibleRates", False))
        seed = uidic.get("rateSeed")
        if seed is not None:
            rs["rate_seed"] = int(seed)

    if method not in ["historical average", "historical", "histochastic"]:
        rs["from"] = FROM
        rs["to"] = date.today().year - 1
