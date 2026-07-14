"""
Pydantic schema for the structured plan explanation.

PlanExplanation is the versioned contract between the explanation engine
(owlplanner.assistant.explain.build_explanation) and its consumers — the
explain_results MCP tool and, through it, LLM assistants.  Field descriptions
double as the machine-readable documentation of that contract; the in-payload
"note" strings carry interpretation guidance that travels with the data.

build_explanation validates every explanation through this schema at
construction time, so a drift between the engine and the contract fails fast
in tests rather than surfacing as a malformed tool response.  Bump
SCHEMA_VERSION when making a change that could break a consumer (renaming or
removing a field, changing units or sign conventions); adding optional fields
is backward-compatible and needs no bump.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class PersonActions(BaseModel):
    """One person's executed decisions for the first plan year (today's dollars)."""

    model_config = ConfigDict(extra="forbid")

    person: str = Field(description="Person's name as configured in the plan.")
    age: int = Field(description="Age reached during the first plan year.")
    roth_conversion: float = Field(description="Roth conversion to execute this year.")
    withdrawals: Dict[str, float] = Field(
        description="Withdrawals by account: taxable, tax_deferred, roth, hsa."
    )
    rmd_required: float = Field(description="Required minimum distribution due this year.")


class ThisYearActions(BaseModel):
    """The household's executed decisions for the first plan year (today's dollars)."""

    model_config = ConfigDict(extra="forbid")

    per_person: List[PersonActions] = Field(description="Per-person conversions, withdrawals, and RMDs.")
    net_spending: float = Field(description="Net (after-tax) spending for the year.")
    surplus_deposit: float = Field(description="Surplus deposited into taxable savings at year end.")


class Year0Bracket(BaseModel):
    """Federal ordinary-income bracket position in the first plan year."""

    model_config = ConfigDict(extra="forbid")

    top_bracket_rate_pct: float = Field(description="Marginal rate of the highest bracket reached (%).")
    headroom_in_bracket: float = Field(description="Room left below the bracket's upper edge (today's $).")
    filled_to_boundary: bool = Field(
        description="True when the optimizer deliberately fills the bracket to its edge."
    )


class ThisYear(BaseModel):
    """First plan year: the only decisions that are executed. Lead the narration here."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(description="Calendar year of the first plan year.")
    actions: ThisYearActions = Field(description="Decisions to execute now.")
    tax_bracket: Optional[Year0Bracket] = Field(
        default=None, description="Ordinary-income bracket position this year."
    )
    threshold_proximity: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Primal headroom to tax cliffs (niit, irmaa with two-year lookback, aca, "
        "social_security). Cliffs are reported as headroom, not marginal prices.",
    )
    marginal_values: Optional[Dict[str, float]] = Field(
        default=None,
        description="Marginal values for this year: value_of_extra_dollar_now (year-1 cash-flow "
        "dual) and value_per_dollar_of_extra_conversion_cap when the cap binds.",
    )
    note: str = Field(description="Framing note: later years are projections, re-solve yearly.")


class BindingConstraint(BaseModel):
    """A policy-class constraint active at a bound with a significant shadow price."""

    model_config = ConfigDict(extra="forbid")

    constraint: str = Field(description="Tag family plus indices, e.g. rmd[0,7].")
    side: str = Field(description="Which bound is active: lower, upper, or equality.")
    description: Optional[str] = Field(default=None, description="Human-readable constraint label.")


class RothConversionEntry(BaseModel):
    """One year's Roth conversion in the schedule."""

    model_config = ConfigDict(extra="forbid")

    person: str = Field(description="Person converting.")
    year: int = Field(description="Calendar year of the conversion.")
    amount_today: float = Field(description="Conversion amount (today's $).")


class RothConversions(BaseModel):
    """The conversion schedule and, when a cap binds, its marginal value."""

    model_config = ConfigDict(extra="forbid")

    schedule_today_dollars: List[RothConversionEntry] = Field(description="Per-year conversion schedule.")
    total_converted_today: float = Field(description="Total converted over the plan (today's $).")
    cap_binding_years: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Years where the conversion cap binds, with the value per dollar of extra cap.",
    )
    note: Optional[str] = Field(default=None, description="Interpretation of cap_binding_years.")


class BracketYear(BaseModel):
    """One year's federal ordinary-income bracket fill."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(description="Calendar year.")
    top_bracket_rate_pct: float = Field(description="Marginal rate of the highest bracket reached (%).")
    headroom_in_bracket_today: float = Field(description="Room left in that bracket (today's $).")
    filled_to_boundary: bool = Field(description="True when the bracket is filled to its edge.")


class TaxBrackets(BaseModel):
    """Per-year federal bracket fill; boundary years mark deliberate bracket-filling."""

    model_config = ConfigDict(extra="forbid")

    by_year: List[BracketYear] = Field(description="Bracket reached and headroom, per year.")
    note: str = Field(description="Interpretation guidance.")


class DepletionEvent(BaseModel):
    """First year an initially-funded account reaches zero."""

    model_config = ConfigDict(extra="forbid")

    person: str = Field(description="Account owner.")
    account: str = Field(description="Account type: taxable, tax_deferred, roth, or hsa.")
    depleted_in: int = Field(description="Calendar year the account is emptied.")


class AccountDepletion(BaseModel):
    """Account depletion order — the withdrawal sequencing the optimizer chose."""

    model_config = ConfigDict(extra="forbid")

    events: List[DepletionEvent] = Field(description="Depletion events in the primal solution.")
    note: str = Field(description="Interpretation guidance.")


class ShadowPrices(BaseModel):
    """Marginal values of active goals and rules, in the reported-objective units.

    Known sections are typed below; additional keys are policy constraint-tag or
    column-bound families reported generically as {binding_rows|binding_bounds, note}
    (see CONSTRAINT_FAMILIES and COLUMN_FAMILIES in owlplanner.assistant.explain).
    """

    model_config = ConfigDict(extra="allow")

    bequest_floor: Optional[Dict[str, Any]] = Field(
        default=None, description="Lifetime-spending cost per today's-$ of required bequest."
    )
    spending_floor: Optional[Dict[str, Any]] = Field(
        default=None, description="Bequest cost per dollar of required first-year spending (maxBequest)."
    )
    value_of_extra_income_by_year: Optional[Dict[str, Any]] = Field(
        default=None, description="The plan's endogenous discount curve from the cash-flow duals."
    )
    rmd_floors: Optional[Dict[str, Any]] = Field(
        default=None, description="Years where RMDs force withdrawals, and the cost per forced dollar."
    )
    spending_profile_band: Optional[Dict[str, Any]] = Field(
        default=None, description="Years pinned at the spending-profile slack band edges."
    )


class PlanExplanation(BaseModel):
    """Structured explanation of a solved plan, grounded in LP shadow prices.

    All sensitivities are marginal, hold discrete choices and self-consistent tax
    quantities fixed, and are expressed in sensitivity_units unless a key says
    otherwise. this_year comes first: only first-year decisions are executed.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=SCHEMA_VERSION, description="Contract version of this payload.")
    objective: str = Field(description="Solved objective: maxSpending or maxBequest.")
    sensitivity_units: str = Field(description="Units of all shadow prices and marginal values.")
    this_year: ThisYear = Field(description="Executed decisions — narrate these first.")
    shadow_prices: ShadowPrices = Field(description="Marginal values of active goals and rules.")
    binding_constraints: List[BindingConstraint] = Field(description="Active policy constraints.")
    roth_conversions: RothConversions = Field(description="Conversion schedule and cap analysis.")
    tax_brackets: TaxBrackets = Field(description="Per-year bracket fill.")
    account_depletion: AccountDepletion = Field(description="Withdrawal sequencing.")
    caveats: List[str] = Field(description="Scope-of-validity notes the narration must respect.")


def plan_explanation_json_schema() -> dict:
    """JSON Schema of the explanation payload, for documentation and MCP consumers."""
    return PlanExplanation.model_json_schema()
