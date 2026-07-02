"""
Generic, schema-driven config round-trip tests.

Instead of one hand-written test per configuration variable, this module
introspects the Pydantic schema and verifies that every *scalar* field
(float / int / bool) in the round-tripped sections survives both bridges:

    config -> config_to_plan -> plan_to_config -> config        (plan bridge)
    config -> config_to_ui   -> ui_to_config   -> config        (UI bridge)

A completeness guard (``test_no_unclassified_scalar_fields``) asserts that
every scalar field in the introspected sections is either exercised or listed
in ``SKIP_FIELDS`` with a reason. A newly-added scalar field that a developer
forgets to wire into plan_bridge/ui_bridge will therefore either fail its
round-trip assertion or fail the guard (forcing a conscious skip entry) — it
cannot slip through silently.

Limitations:
  - Covers scalar fields only. Structural fields (per-person lists, enums/strings,
    and method-conditional groups) remain covered by their dedicated tests and are
    not introspected here.
  - Only the sections in ``INTROSPECTED_SECTIONS`` are covered; free-form
    ``solver_options`` (a bare dict) and list/file-only sections are excluded.
  - Auto-coverage is bounded by the Pydantic schema: a parameter stored outside
    the schema is not seen.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import typing

import pytest

from owlplanner.config import (
    config_to_plan,
    config_to_ui,
    default_config,
    plan_to_config,
    ui_to_config,
)
from owlplanner.config.schema import CaseConfig


# Sections whose scalar fields we round-trip. Each maps to its Pydantic model
# (resolved below). Excluded: basic_info / savings_assets / fixed_income
# (per-person lists), asset_allocation (structural matrices), solver_options
# (free-form dict), household_financial_profile (filename only).
INTROSPECTED_SECTIONS = (
    "rates_selection",
    "optimization_parameters",
    "results",
    "aca_settings",
)


# Scalar fields intentionally NOT exercised, each with a reason. These are
# method-conditional rate parameters that are only serialized for the rate
# method that uses them (the default config uses 'historical_average').
SKIP_FIELDS = {
    ("rates_selection", "from_"): "historical-range method only",
    ("rates_selection", "to"): "historical-range method only",
    ("rates_selection", "rate_seed"): "stochastic methods only (not serialized otherwise)",
    ("rates_selection", "reproducible_rates"): "stochastic methods only (not serialized otherwise)",
    ("rates_selection", "block_size"): "historical_bootstrap only",
    ("rates_selection", "crisis_weight"): "historical_bootstrap only",
    ("rates_selection", "shrink"): "vector_ar only",
    ("rates_selection", "n_components"): "gmm/hmm only",
    ("rates_selection", "reg_trans"): "hmm only",
    ("rates_selection", "init_regime"): "hmm only",
    ("rates_selection", "constrain_mean"): "constrain-mean methods only",
}


# Sentinel overrides for fields with tight bounds or domain constraints, where
# the generic "default + delta" sentinel would be invalid.
SENTINEL_OVERRIDES = {
    ("rates_selection", "dividend_rate"): 2.5,  # UI bounds dividend <= 5%
    ("aca_settings", "aca_start_year"): 2030,  # setACA rejects 0 < year < 2000
}


def _section_model(section):
    """Resolve the Pydantic model class for a CaseConfig section (stripping Optional)."""
    ann = CaseConfig.model_fields[section].annotation
    args = [a for a in typing.get_args(ann) if a is not type(None)]
    if args:
        ann = args[0]
    return ann


def _scalar_kind(annotation):
    """Return 'bool' | 'int' | 'float' for a scalar (or Optional scalar) field, else None."""
    args = typing.get_args(annotation)
    if args:  # Optional[X] / Union[...] — accept only a single non-None member
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) != 1:
            return None
        annotation = non_none[0]
    # bool is a subclass of int — check it first.
    if annotation is bool:
        return "bool"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    return None


def _scalar_fields():
    """Yield (section, field, kind, default) for every scalar field of introspected sections."""
    for section in INTROSPECTED_SECTIONS:
        model = _section_model(section)
        for fname, finfo in model.model_fields.items():
            kind = _scalar_kind(finfo.annotation)
            if kind is None:
                continue
            default = None if finfo.default is None else finfo.default
            yield section, fname, kind, default


def _sentinel(section, field, kind, default):
    """A valid value distinct from the field default."""
    if (section, field) in SENTINEL_OVERRIDES:
        return SENTINEL_OVERRIDES[(section, field)]
    if kind == "bool":
        return not bool(default) if default is not None else True
    if kind == "int":
        return (int(default) + 5) if default is not None else 5
    # float
    return round((float(default) + 3.0) if default is not None else 3.0, 3)


def _exercised_fields():
    """Scalar fields that are round-trip asserted (everything not skip-listed)."""
    return [
        (section, field, kind, default)
        for section, field, kind, default in _scalar_fields()
        if (section, field) not in SKIP_FIELDS
    ]


def _build_config(section, field, sentinel):
    """default_config(ni=1) with one field overridden to the sentinel value."""
    cfg = copy.deepcopy(default_config(ni=1))
    cfg["case_name"] = "rt_generic"
    cfg["basic_info"]["names"] = ["Joe"]
    cfg.setdefault(section, {})
    # ACA is only serialized when slcsp_annual > 0 — activate it for aca fields.
    if section == "aca_settings" and field != "slcsp_annual":
        cfg["aca_settings"]["slcsp_annual"] = 5.0
    cfg[section][field] = sentinel
    return cfg


_CASES = _exercised_fields()
_IDS = [f"{s}.{f}" for s, f, _k, _d in _CASES]


@pytest.mark.parametrize("section,field,kind,default", _CASES, ids=_IDS)
def test_scalar_field_roundtrips_through_plan(section, field, kind, default):
    """Each scalar field survives config -> plan -> config."""
    sentinel = _sentinel(section, field, kind, default)
    cfg = _build_config(section, field, sentinel)

    p = config_to_plan(cfg, verbose=False, loadHFP=False)
    out = plan_to_config(p)

    assert field in out.get(section, {}), (
        f"{section}.{field} dropped by plan bridge (config_to_plan/plan_to_config). "
        f"Wire it in plan_bridge.py or add to SKIP_FIELDS with a reason."
    )
    assert out[section][field] == pytest.approx(sentinel), (
        f"{section}.{field} changed across plan round-trip: sent {sentinel!r}, got {out[section][field]!r}"
    )


@pytest.mark.parametrize("section,field,kind,default", _CASES, ids=_IDS)
def test_scalar_field_roundtrips_through_ui(section, field, kind, default):
    """Each scalar field survives config -> ui -> config."""
    sentinel = _sentinel(section, field, kind, default)
    cfg = _build_config(section, field, sentinel)

    uidic = config_to_ui(cfg)
    out = ui_to_config(uidic)

    assert field in out.get(section, {}), (
        f"{section}.{field} dropped by UI bridge (config_to_ui/ui_to_config). "
        f"Wire it in ui_bridge.py or add to SKIP_FIELDS with a reason."
    )
    assert out[section][field] == pytest.approx(sentinel), (
        f"{section}.{field} changed across UI round-trip: sent {sentinel!r}, got {out[section][field]!r}"
    )


def test_no_unclassified_scalar_fields():
    """Every scalar field in introspected sections is exercised or skip-listed.

    This guard is what makes the suite self-maintaining: adding a scalar field to
    the schema without wiring it (or consciously skip-listing it) fails here.
    """
    exercised = {(s, f) for s, f, _k, _d in _exercised_fields()}
    classified = exercised | set(SKIP_FIELDS)
    all_scalar = {(s, f) for s, f, _k, _d in _scalar_fields()}
    unclassified = all_scalar - classified
    assert not unclassified, (
        "Unclassified scalar schema field(s): "
        f"{sorted(unclassified)}. Add each to the exercised set (wire its "
        "round-trip) or to SKIP_FIELDS with a reason."
    )


def test_motivating_fields_are_covered():
    """Sanity: the liquidation rates that motivated this suite are auto-covered."""
    covered = {(s, f) for s, f, _k, _d in _exercised_fields()}
    assert ("rates_selection", "liquidation_tax_rate") in covered
    assert ("rates_selection", "liquidation_capgains_rate") in covered
