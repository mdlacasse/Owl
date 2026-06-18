"""
Tests for config <-> UI flat dict conversion (owlplanner.config.ui_bridge).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

from io import StringIO

import pytest
import owlplanner as owl
from owlplanner.mylogging import Logger
from owlplanner.config import (
    apply_config_to_plan,
    config_to_plan,
    config_to_ui,
    load_toml,
    plan_to_config,
    sanitize_config,
    save_toml,
    ui_to_config,
)
from owlplanner.config.schema import parse_solver_options
from owlplanner.rate_models.constants import CONSTRAIN_MEAN_METHODS


def test_sanitize_config_start_roth_past_year():
    """sanitize_config resets startRothConversions to this year when in the past."""
    from datetime import date

    diconf = {"solver_options": {"startRothConversions": 2019}}
    log = StringIO()
    mylog = Logger(verbose=True, logstreams=[log, log])
    sanitize_config(diconf, mylog=mylog)
    thisyear = date.today().year

    assert diconf["solver_options"]["startRothConversions"] == thisyear
    assert "past" in log.getvalue()
    assert "reset to" in log.getvalue()


def test_sanitize_config_default_translated_to_trailing_30():
    """sanitize_config translates deprecated method=default to trailing-30 (backward compat)."""
    diconf = {"rates_selection": {"method": "default"}}
    sanitize_config(diconf)
    assert diconf["rates_selection"]["method"] == "trailing_30"


def test_load_toml_start_roth_past_year_reset():
    """startRothConversions in the past is reset when config file is read (via sanitize_config)."""
    from datetime import date

    toml_content = open("examples/Case_joe.toml").read()
    toml_content = toml_content.replace(
        "startRothConversions = 2026",
        "startRothConversions = 2019",  # Past year
    )
    log = StringIO()
    mylog = Logger(verbose=True, logstreams=[log, log])
    diconf, _, _ = load_toml(StringIO(toml_content), mylog=mylog)
    thisyear = date.today().year

    assert diconf["solver_options"]["startRothConversions"] == thisyear
    assert "past" in log.getvalue()


def test_ui_to_config_linear_omits_interpolation_center_width():
    """linear UI output omits interpolation_center/width (not used by the plan)."""
    diconf = _minimal_config_for_rates()
    diconf["asset_allocation"]["interpolation_method"] = "linear"
    diconf["asset_allocation"].pop("interpolation_center", None)
    diconf["asset_allocation"].pop("interpolation_width", None)

    uidic = config_to_ui(diconf)
    assert uidic["interpMethod"] == "linear"

    out = ui_to_config(uidic)
    assert "interpolation_center" not in out["asset_allocation"]
    assert "interpolation_width" not in out["asset_allocation"]

    plan = config_to_plan(out, verbose=False, loadHFP=False)
    assert plan.interpMethod == "linear"


def test_config_to_ui_roundtrip():
    """config -> ui -> config preserves structure."""
    diconf, _, _ = load_toml(StringIO(open("examples/Case_joe.toml").read()))
    uidic = config_to_ui(diconf)

    assert uidic["name"] == "joe"
    assert uidic["status"] == "single"
    assert uidic["iname0"] == "Joe"
    assert uidic["allocType"] == "individual"

    back = ui_to_config(uidic)
    assert back["case_name"] == "joe"
    assert back["basic_info"]["names"] == ["Joe"]
    assert back["asset_allocation"]["type"] == "individual"


def test_ui_to_config_to_plan():
    """ui dict -> config -> plan produces valid plan."""
    diconf, _, _ = load_toml(StringIO(open("examples/Case_joe.toml").read()))
    uidic = config_to_ui(diconf)
    back = ui_to_config(uidic)
    plan = config_to_plan(back, verbose=False, loadHFP=False)

    assert plan._name == "joe"
    assert plan.N_i == 1
    assert plan.inames[0] == "Joe"


def test_config_to_ui_dataframe_maps_to_user():
    """When config has method=dataframe, config_to_ui maps to user and logs warning."""

    diconf = {
        "case_name": "test",
        "description": "",
        "basic_info": {
            "status": "single",
            "names": ["Joe"],
            "date_of_birth": ["1961-01-15"],
            "life_expectancy": [89],
            "start_date": "today",
        },
        "savings_assets": {
            "taxable_savings_balances": [100],
            "tax_deferred_savings_balances": [200],
            "tax_free_savings_balances": [50],
        },
        "household_financial_profile": {"HFP_file_name": "None"},
        "fixed_income": {
            "pension_monthly_amounts": [0],
            "pension_ages": [65],
            "pension_indexed": [True],
            "social_security_pia_amounts": [0],
            "social_security_ages": [67],
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": 30,
            "dividend_rate": 1.8,
            "obbba_expiration_year": 2032,
            "method": "dataframe",
        },
        "asset_allocation": {
            "interpolation_method": "s-curve",
            "interpolation_center": 15,
            "interpolation_width": 5,
            "type": "individual",
            "generic": [[[60, 40, 0, 0], [70, 30, 0, 0]]],
        },
        "optimization_parameters": {
            "spending_profile": "flat",
            "surviving_spouse_spending_percent": 60,
            "objective": "maxSpending",
        },
        "solver_options": {},
        "results": {"default_plots": "nominal"},
    }
    log = StringIO()
    mylog = Logger(verbose=True, logstreams=[log, log])
    uidic = config_to_ui(diconf, mylog=mylog)

    assert uidic["rateType"] == "constant"
    assert uidic["fixedType"] == "user"
    assert "Dataframe rate method is not supported in UI" in log.getvalue()


def test_config_roundtrip_social_security_trim():
    """SS trim_pct and trim_year roundtrip through config_to_ui and ui_to_config."""
    diconf = _minimal_config_for_rates()
    diconf["fixed_income"]["social_security_trim_pct"] = 23
    diconf["fixed_income"]["social_security_trim_year"] = 2035

    uidic = config_to_ui(diconf)
    assert uidic["ssTrimPct"] == 23
    assert uidic["ssTrimYear"] == 2035

    out = ui_to_config(uidic)
    assert out["fixed_income"]["social_security_trim_pct"] == 23
    assert out["fixed_income"]["social_security_trim_year"] == 2035


def test_plan_to_config_saves_trim_when_nonzero():
    """plan_to_config includes trim_pct and trim_year in fixed_income when trim_pct > 0."""
    from owlplanner.config import plan_to_config

    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("gaussian", values=[7.0, 4.0, 3.3, 2.8], stdev=[17.0, 8.0, 10.0, 3.0])
    p.setSocialSecurity([2000], [67], trim_pct=23, trim_year=2035)

    out = plan_to_config(p)
    assert out["fixed_income"]["social_security_trim_pct"] == 23
    assert out["fixed_income"]["social_security_trim_year"] == 2035


def test_plan_to_config_omits_trim_when_zero():
    """plan_to_config omits trim keys when trim_pct is 0 (default)."""
    from owlplanner.config import plan_to_config

    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("gaussian", values=[7.0, 4.0, 3.3, 2.8], stdev=[17.0, 8.0, 10.0, 3.0])
    p.setSocialSecurity([2000], [67])  # default trim_pct=0

    out = plan_to_config(p)
    assert "social_security_trim_pct" not in out["fixed_income"]
    assert "social_security_trim_year" not in out["fixed_income"]


def test_worksheet_real_dollars_ui_to_config_and_apply():
    """UI worksheetRealDollars round-trips through ui_to_config and apply_config_to_plan."""
    diconf = _minimal_config_for_rates()
    uidic = config_to_ui(diconf)
    uidic["worksheetRealDollars"] = True

    out = ui_to_config(uidic)
    assert out["results"]["worksheet_real_dollars"] is True

    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("trailing_30")
    if not hasattr(p, "solverOptions"):
        p.solverOptions = {}
    p.setWorksheetRealDollars(False)

    apply_config_to_plan(p, out)
    assert p.worksheetRealDollars is True


def test_apply_config_to_plan():
    """apply_config_to_plan syncs config to existing plan."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("trailing_30")
    if not hasattr(p, "solverOptions"):
        p.solverOptions = {}

    diconf = plan_to_config(p)
    diconf["savings_assets"]["taxable_savings_balances"] = [150.0]  # Change

    apply_config_to_plan(p, diconf)
    assert p.beta_ij[0, 0] == 150_000  # 150 * 1000


def test_config_to_ui_rates_in_valid_range():
    """
    Regression: config_to_ui must produce rate values in valid widget range.

    Bug (StreamlitValueAboveMaxError): config stored rates in percent (7 = 7%),
    but config_to_ui incorrectly multiplied by 100, producing fxRate0=700 which
    exceeded st.number_input max_value=100. Returns and volatility use percent;
    correlations use Pearson coefficient (-1 to 1).
    """
    diconf = _minimal_config_for_rates()
    diconf["rates_selection"]["method"] = "user"
    diconf["rates_selection"]["values"] = [7.0, 4.0, 3.3, 2.8]

    uidic = config_to_ui(diconf)

    # Returns: percent (e.g., 7 for 7%). Must be in [-100, 100] for widget.
    for k in range(4):
        val = uidic[f"fxRate{k}"]
        assert -100 <= val <= 100, f"fxRate{k}={val} out of widget range [-100, 100]"
    assert uidic["fxRate0"] == 7.0
    assert uidic["fxRate1"] == 4.0


def test_config_to_ui_gaussian_rates_in_valid_range():
    """
    Regression: gaussian rates (means, stdev, corr) in valid ranges after config_to_ui.

    Means and stdev: percent. Correlations: Pearson coefficient (-1 to 1).
    """
    diconf = _minimal_config_for_rates()
    diconf["rates_selection"]["method"] = "gaussian"
    diconf["rates_selection"]["values"] = [8.0, 5.0, 3.5, 2.5]
    diconf["rates_selection"]["standard_deviations"] = [17.0, 8.0, 10.0, 3.0]
    diconf["rates_selection"]["correlations"] = [0.4, 0.26, -0.22, 0.84, -0.39, -0.39]

    uidic = config_to_ui(diconf)

    # Means: percent, in [-100, 100]
    for k in range(4):
        assert -100 <= uidic[f"mean{k}"] <= 100, f"mean{k} out of range"
    assert uidic["mean0"] == 8.0

    # Stdev: percent, non-negative
    for k in range(4):
        assert 0 <= uidic[f"stdev{k}"] <= 100, f"stdev{k} out of range"
    assert uidic["stdev0"] == 17.0

    # Correlations: coefficient (-1 to 1), not percent
    for q in range(1, 7):
        assert -1 <= uidic[f"corr{q}"] <= 1, f"corr{q} must be coefficient in [-1, 1]"
    assert abs(uidic["corr1"] - 0.4) < 1e-9


def test_plan_to_config_to_ui_rates_roundtrip():
    """
    Regression: plan -> config -> ui preserves rate representation.
    plan_to_config saves percent for returns/stdev, coefficient for corr.
    config_to_ui must not double-convert (e.g., multiply percent by 100 again).
    """
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("gaussian", values=[7.0, 4.0, 3.3, 2.8], stdev=[17.0, 8.0, 10.0, 3.0])

    diconf = plan_to_config(p)
    uidic = config_to_ui(diconf)

    # Plan had 7% etc.; config and UI should show 7, not 700
    assert uidic["mean0"] == 7.0
    assert uidic["stdev0"] == 17.0
    assert all(-100 <= uidic[f"mean{k}"] <= 100 for k in range(4))
    assert all(0 <= uidic[f"stdev{k}"] <= 100 for k in range(4))


def test_config_to_plan_normalizes_empty_hfp_filename():
    """Empty HFP_file_name must not be treated as a path (no FileNotFoundError)."""
    diconf = _minimal_config_for_rates()
    diconf["rates_selection"]["values"] = [7.0, 4.0, 3.3, 2.8]
    diconf["household_financial_profile"] = {"HFP_file_name": ""}
    p = config_to_plan(diconf, verbose=False, loadHFP=True)
    assert p.hfpFileName == "None"


def test_config_to_plan_normalizes_dictionary_of_dataframes_hfp():
    """Legacy/in-memory marker string is not a filesystem path."""
    diconf = _minimal_config_for_rates()
    diconf["rates_selection"]["values"] = [7.0, 4.0, 3.3, 2.8]
    diconf["household_financial_profile"] = {"HFP_file_name": "dictionary of DataFrames"}
    p = config_to_plan(diconf, verbose=False, loadHFP=True)
    assert p.hfpFileName == "None"


def test_plan_to_config_normalizes_in_memory_hfp_marker():
    """plan_to_config must not persist hfp_io.read's dict-input placeholder as a path."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setRates("user", values=[7.0, 4.0, 3.3, 2.8])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.hfpFileName = "dictionary of DataFrames"
    out = plan_to_config(p)
    assert out["household_financial_profile"]["HFP_file_name"] == "None"


def test_solver_options_passthrough_roundtrip():
    """solver_options passthrough keys survive config_to_ui -> ui_to_config."""
    diconf = _minimal_config_for_rates()
    raw_so = {
        "timePreference": 2.5,
        "gap": 1e-3,
        "verbose": True,
        "epsilon": 0.01,
        "bendersMaxIter": 40,
        "swapRothConverters": 1,
        "fixedSpending": 80.0,
        "units": "k",
        "bigMaca": 1e8,
        "bigMss": 9e7,
        "bigMltcg": 5e6,
        "bigMniit": 4e6,
        "withLTCG": "optimize",
        "withNIIT": "loop",
    }
    diconf["solver_options"] = raw_so
    uidic = config_to_ui(diconf)
    assert uidic["timePreference"] == 2.5
    assert uidic["optimizeLTCG"] is True
    assert uidic["optimizeNIIT"] is False

    back = ui_to_config(uidic)
    so_in = parse_solver_options(raw_so)
    so_out = parse_solver_options(back["solver_options"])
    for k in raw_so:
        assert so_out[k] == so_in[k], k


def test_solver_options_with_ss_ages_married_optimize_roundtrip():
    """withSSAges optimize round-trips for married (UI uses ssAgesMode both)."""
    diconf = _minimal_married_config()
    diconf["solver_options"] = {"withSSAges": "optimize"}
    uidic = config_to_ui(diconf)
    assert uidic["ssAgesMode"] == "both"

    back = ui_to_config(uidic)
    assert back["solver_options"]["withSSAges"] == "optimize"


def test_swap_roth_converters_disabled_by_default():
    """With no swapRothConverters set, the UI toggle is off and config round-trips to 0."""
    diconf = _minimal_married_config()
    diconf["solver_options"] = {}
    uidic = config_to_ui(diconf)
    assert uidic["swapRothConvertersEnabled"] is False

    back = ui_to_config(uidic)
    assert back["solver_options"]["swapRothConverters"] == 0


@pytest.mark.parametrize("first_index,sign", [(0, 1), (1, -1)])
def test_swap_roth_converters_bidirectional_mapping(first_index, sign):
    """swapRothConverters <-> swapRothConvertersEnabled/First/Year round-trips with correct sign."""
    diconf = _minimal_married_config()
    diconf["solver_options"] = {"swapRothConverters": sign * 2032}
    uidic = config_to_ui(diconf)
    assert uidic["swapRothConvertersEnabled"] is True
    assert uidic["swapRothConvertersYear"] == 2032
    assert uidic["swapRothConvertersFirst"] == diconf["basic_info"]["names"][first_index]

    back = ui_to_config(uidic)
    assert back["solver_options"]["swapRothConverters"] == sign * 2032


def test_max_roth_conversion_file_no_longer_supported():
    """Legacy maxRothConversion = 'file' is no longer auto-migrated (breaking change);
    it now fails schema validation with a clear error, pointing users to
    useRothConvOverrides + the "Roth conv" column instead."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        parse_solver_options({"maxRothConversion": "file", "bequest": 100})


def test_roth_conv_overrides_disabled_by_default():
    """With no useRothConvOverrides set, the key is simply absent from both dicts (defaults to False)."""
    diconf = _minimal_married_config()
    diconf["solver_options"] = {}
    uidic = config_to_ui(diconf)
    assert "useRothConvOverrides" not in uidic

    back = ui_to_config(uidic)
    assert "useRothConvOverrides" not in back["solver_options"]


def test_roth_conv_overrides_bidirectional_mapping():
    """useRothConvOverrides round-trips between config and UI under the same name."""
    diconf = _minimal_married_config()
    diconf["solver_options"] = {"useRothConvOverrides": True}
    uidic = config_to_ui(diconf)
    assert uidic["useRothConvOverrides"] is True

    back = ui_to_config(uidic)
    assert back["solver_options"]["useRothConvOverrides"] is True


def test_solver_options_with_ss_ages_single_name_roundtrip():
    """withSSAges single-name string round-trips: "Joe" → ssAgesMode "Joe" → "Joe"."""
    diconf = _minimal_married_config()
    iname0 = diconf["basic_info"]["names"][0]
    diconf["solver_options"] = {"withSSAges": iname0}
    uidic = config_to_ui(diconf)
    assert uidic["ssAgesMode"] == iname0

    back = ui_to_config(uidic)
    assert back["solver_options"]["withSSAges"] == iname0


def test_taxable_cost_basis_config_to_ui_roundtrip():
    """taxable_cost_basis round-trips through config_to_ui and ui_to_config."""
    diconf = _minimal_config_for_rates()
    diconf["savings_assets"]["taxable_cost_basis"] = [45.0]

    uidic = config_to_ui(diconf)
    assert uidic["txblBasis0"] == 45.0

    out = ui_to_config(uidic)
    assert out["savings_assets"]["taxable_cost_basis"] == [45.0]


def test_taxable_cost_basis_ui_zeros_written():
    """All-zero UI basis fields are still written to config (explicit legacy choice, not silent default)."""
    diconf = _minimal_config_for_rates()
    uidic = config_to_ui(diconf)
    uidic["txblBasis0"] = 0.0
    out = ui_to_config(uidic)
    assert "taxable_cost_basis" in out["savings_assets"]
    assert out["savings_assets"]["taxable_cost_basis"] == [0.0]


def test_apply_config_clears_basis_when_ui_zeros():
    """apply_config_to_plan clears in-memory basis when config omits taxable_cost_basis."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setCostBasis([45.0])

    diconf = plan_to_config(p)
    del diconf["savings_assets"]["taxable_cost_basis"]
    apply_config_to_plan(p, diconf)
    assert p.taxable_basis_i is None
    assert p.gain_fraction_in is None


def test_other_medical_expenses_plan_to_config_roundtrip():
    """setMedicalExpenses round-trips through plan_to_config and back to the plan."""
    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    p.setMedicalExpenses(5.0)  # $5k/year

    out = plan_to_config(p)
    assert out["optimization_parameters"]["other_medical_expenses"] == 5.0

    p2 = config_to_plan(out, verbose=False)
    assert p2.other_medical_k == 5000.0, f"Expected other_medical_k=5000.0, got {p2.other_medical_k}"


def test_other_medical_expenses_default_zero():
    """other_medical_expenses defaults to 0.0 and is omitted from plan_to_config when unset."""
    diconf = _minimal_config_for_rates()
    uidic = config_to_ui(diconf)
    assert uidic["otherMedical"] == 0.0

    p = owl.Plan(["Joe"], ["1961-01-15"], [80], "test", verbose=False)
    p.setSpendingProfile("flat")
    p.setAccountBalances(taxable=[100], taxDeferred=[200], taxFree=[50])
    p.setAllocationRatios("individual", generic=[[[60, 40, 0, 0], [70, 30, 0, 0]]])
    p.setRates("user", values=[6.0, 4.0, 3.0, 2.5])
    out = plan_to_config(p)
    assert out["optimization_parameters"].get("other_medical_expenses", 0.0) == 0.0


def test_solver_ui_passthrough_keys_match_plan_known_options():
    """SOLVER_UI_PASSTHROUGH_KEYS must each appear in Plan.solve knownOptions (no typos / drift)."""
    from owlplanner.config.ui_bridge import SOLVER_UI_PASSTHROUGH_KEYS

    # Subset of src/owlplanner/plan.py solve() knownOptions for passthrough scalars.
    # swapRothConverters is intentionally excluded: it is derived from
    # swapRothConvertersEnabled/First/Year (see config_to_ui / ui_to_config).
    plan_known = {
        "absTol", "amoConstraints", "amoRoth", "amoSurplus", "bequest", "bigMaca", "bigMamo",
        "bigMltcg", "bigMniit", "bigMss", "bendersMaxIter", "epsilon", "fixedSpending", "gap",
        "maxIter", "maxRothConversion", "maxTime", "netSpending", "noLateSurplus",
        "noRothConversions", "oppCostX", "relTol", "solver", "spendingSlack",
        "startRothConversions", "timePreference", "units", "useRothConvOverrides", "verbose",
        "withSCLoop",
    }
    assert set(SOLVER_UI_PASSTHROUGH_KEYS) == plan_known


@pytest.mark.parametrize("method", CONSTRAIN_MEAN_METHODS)
def test_rate_bool_optional_params_survive_ui_roundtrip(method):
    """All bool optional_parameters survive config → ui → config for each constrain-mean method.

    Introspects the model's optional_parameters so the test automatically covers any
    new boolean flag added to a rate model — it will fail until ui_bridge.py is updated.
    """
    from owlplanner.rate_models.loader import load_rate_model

    ModelClass = load_rate_model(method)
    # Skip params explicitly marked ui_excluded: these are numerical knobs intentionally
    # not surfaced in the UI (TOML/API only), so they are not expected to round-trip.
    bool_params = {
        k: v["default"]
        for k, v in ModelClass.optional_parameters.items()
        if v.get("type") == "bool" and not v.get("ui_excluded", False)
    }
    if not bool_params:
        pytest.skip(f"No bool optional_parameters for method={method!r}")

    diconf = _minimal_config_for_rates()
    diconf["rates_selection"]["method"] = method
    for param, default in bool_params.items():
        diconf["rates_selection"][param] = not default  # flip every boolean default

    uidic = config_to_ui(diconf)
    out = ui_to_config(uidic)

    for param, default in bool_params.items():
        expected = not default
        assert out["rates_selection"].get(param) == expected, (
            f"Bool optional_parameter '{param}' not preserved in ui_bridge "
            f"round-trip for method='{method}'"
        )


def _minimal_married_config():
    """Minimal married two-person config for solver/UI mapping tests."""
    return {
        "case_name": "test",
        "basic_info": {
            "status": "married",
            "names": ["Joe", "Jane"],
            "date_of_birth": ["1961-01-15", "1963-06-01"],
            "life_expectancy": [89, 90],
            "sexes": ["M", "F"],
            "start_date": "today",
        },
        "savings_assets": {
            "taxable_savings_balances": [100, 90],
            "tax_deferred_savings_balances": [200, 180],
            "tax_free_savings_balances": [50, 45],
        },
        "household_financial_profile": {"HFP_file_name": "None"},
        "fixed_income": {
            "pension_monthly_amounts": [0, 0],
            "pension_ages": [65, 65],
            "pension_indexed": [True, True],
            "social_security_pia_amounts": [0, 0],
            "social_security_ages": [67, 67],
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": 30,
            "dividend_rate": 1.8,
            "obbba_expiration_year": 2032,
            "method": "user",
        },
        "asset_allocation": {
            "interpolation_method": "s-curve",
            "interpolation_center": 15,
            "interpolation_width": 5,
            "type": "individual",
            "generic": [
                [[60, 40, 0, 0], [70, 30, 0, 0]],
                [[60, 40, 0, 0], [70, 30, 0, 0]],
            ],
        },
        "optimization_parameters": {
            "spending_profile": "flat",
            "surviving_spouse_spending_percent": 60,
            "objective": "maxSpending",
        },
        "solver_options": {},
        "results": {"default_plots": "nominal"},
    }


def test_state_config_to_ui_roundtrip():
    """basic_info.state round-trips through config_to_ui and ui_to_config."""
    diconf = _minimal_config_for_rates()
    diconf["basic_info"]["state"] = "MN"

    uidic = config_to_ui(diconf)
    assert uidic["state"] == "MN"

    out = ui_to_config(uidic)
    assert out["basic_info"]["state"] == "MN"


def test_state_toml_save_load_roundtrip():
    """basic_info.state survives a save_toml -> load_toml round-trip (empty stays empty)."""
    diconf = _minimal_config_for_rates()
    diconf["basic_info"]["state"] = "MN"

    sio = StringIO()
    save_toml(diconf, sio)
    back, _, _ = load_toml(StringIO(sio.getvalue()))
    assert back["basic_info"]["state"] == "MN"

    # Default (no state set) stays federal-only after a round-trip.
    diconf["basic_info"]["state"] = ""
    sio2 = StringIO()
    save_toml(diconf, sio2)
    back2, _, _ = load_toml(StringIO(sio2.getvalue()))
    assert back2["basic_info"].get("state", "") == ""


def _minimal_config_for_rates():
    """Minimal config dict with rates_selection section."""
    return {
        "case_name": "test",
        "basic_info": {
            "status": "single",
            "names": ["Joe"],
            "date_of_birth": ["1961-01-15"],
            "life_expectancy": [89],
            "start_date": "today",
        },
        "savings_assets": {
            "taxable_savings_balances": [100],
            "tax_deferred_savings_balances": [200],
            "tax_free_savings_balances": [50],
        },
        "household_financial_profile": {"HFP_file_name": "None"},
        "fixed_income": {
            "pension_monthly_amounts": [0],
            "pension_ages": [65],
            "pension_indexed": [True],
            "social_security_pia_amounts": [0],
            "social_security_ages": [67],
        },
        "rates_selection": {
            "heirs_rate_on_tax_deferred_estate": 30,
            "dividend_rate": 1.8,
            "obbba_expiration_year": 2032,
            "method": "user",
        },
        "asset_allocation": {
            "interpolation_method": "s-curve",
            "interpolation_center": 15,
            "interpolation_width": 5,
            "type": "individual",
            "generic": [[[60, 40, 0, 0], [70, 30, 0, 0]]],
        },
        "optimization_parameters": {
            "spending_profile": "flat",
            "surviving_spouse_spending_percent": 60,
            "objective": "maxSpending",
        },
        "solver_options": {},
        "results": {"default_plots": "nominal"},
    }
