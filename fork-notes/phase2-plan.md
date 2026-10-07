# Phase 2 plan: housing ledger and property tax (2026-10-07)

Fork-only planning note. Goal: let the household compare rent and buy, in NY (Yonkers / NYC /
rest of Westchester) or NJ, now or after a later move, with the housing costs and the one state
income-tax rule that depends on them (NJ property tax deduction). Keep it upstream-shaped: exogenous
data in the HFP workbook, a pure LP, nothing optimized about housing itself.

## What upstream already has

Checked in this branch's code; line numbers are this branch's. `debts.py`, `fixedassets.py` and
`hfp_io.py` are identical to upstream `5dd1623` (`git diff`); `export.py` and `ui/owlbridge.py` carry
small fork changes (recapture, moves) that do not touch these features.

| Need | Upstream feature | Where |
|---|---|---|
| Down payment, closing costs, other one-off amounts | `big-ticket items` column (negative = outflow), nominal $ | `plan.py:2047`, `ui/Documentation.py:490` |
| Mortgage | `Debts` sheet: `year`, `term`, `amount`, `rate`; fixed payment subtracted in the cash-flow row; balance left at the end is taken from savings | `debts.py`, `plan.py:3443`, `plan.py:3336` |
| The house as an asset | `Fixed Assets` sheet, `type = residence`: real growth `rate`, sale at `yod` with commission and the §121 exclusion ($250k / $500k), else passed to heirs at the end | `fixedassets.py` |
| Reading a rent-vs-buy result | `final_bequest_today` in `owlcli compare` = savings after heirs' tax − remaining debt + fixed assets kept to the end | `export.py:709`, `export.py:829` |

What is missing:

1. **Recurring housing costs.** Rent, property tax, insurance, maintenance, HOA/condo fees run for
   decades and grow; today they can only be typed as one negative big-ticket cell per year.
2. **Any tax effect of housing.** Upstream assumes the federal standard deduction and has no state
   property-tax rule (`info/modeling-capabilities.md:23,29`; `ui/Documentation.py:548`).

## The maintainer's constraints this plan follows

- Housing is not optimized: his note on Debts ("Should I pay my mortgage or leave my money
  invested?" depends on risk tolerance). Scenarios, not decisions inside the LP.
- State taxes stay a pure LP (#160). No binaries, no new loop parameter.
- Same variables in every state, no lookup between years (#159). Every new quantity is a per-year
  array computed before the solve.
- Data-driven: state rules in `taxes_state.toml`, with sources in comments.
- Contributions go upstream as an issue with a repro and a patch verified on stock `dev`.

## Rule verified for this phase

From the 2025 NJ-1040 instructions (`www.nj.gov/treasury/taxation/pdf/current/1040i.pdf`, pages
25-31), read this session:

- Line 40a: homeowners enter property taxes due and paid on the main home; tenants enter **18% of rent**.
- Line 41: **Property Tax Deduction up to $15,000**, subtracted from line 39 (taxable income) to give
  line 42. It comes **after** the retirement exclusion (lines 28a-28c) and the exemptions, so it
  does not change the income that sets the exclusion tiers.
- Line 56: the alternative is a refundable **$50 Property Tax Credit**; Worksheet H takes the credit
  only when the deduction saves less than $50.
- Eligibility: NJ domicile, main home subject to property tax, line 29 income above the filing
  threshold ($20,000 MFJ); 65+ filers below it get the credit.

The 2020 instructions (`pdf/other_forms/tgi-ee/2020/1040i.pdf`) print the same $15,000, 18% and $50,
so the amounts are nominal (not indexed).

Size, by arithmetic on the NJ MFJ brackets in `taxes_state.toml`: a full $15,000 deduction saves
$525 at 3.5%, $829 at 5.525%, $956 at 6.37% a year. That is the same size as the NJ-vs-NY spread
measured in Phase 1 ($430-1,006/yr), so it belongs in the comparison. A tenant paying $36,000 rent
deducts $6,480.

## Steps

Each step is one commit with its tests; suite and flake8 before each push.

### 1. `Housing` sheet and `housing.py` (new, ~120 lines)

An optional HFP sheet, shaped like `Debts`, one row per recurring cost:

| Column | Meaning |
|---|---|
| `active` | as in `Debts` / `Fixed Assets` |
| `name` | free text |
| `type` | `rent`, `property tax`, `insurance`, `maintenance`, `other` |
| `year` | first year paid |
| `end` | last year paid, inclusive; 0 or negative counts from the plan end as `yod` does (0 = through the last year) |
| `amount` | annual amount in `year` dollars |
| `rate` | real growth above inflation, %; 0 = tracks inflation (as `residence` in `Fixed Assets`) |

`housing.py`, modeled on `debts.py`: `get_housing_arrays(df, N_n, gamma_n, thisyear)` returns
nominal per-year arrays `total_n`, `property_tax_n`, `rent_n`. The Plan stores them as
`housing_costs_n`, `housing_property_tax_n`, `housing_rent_n`, filled in
`processDebtsAndFixedAssets()` next to the debts (same `thisyear`, same `gamma_n` source).

Conventions to document: amounts are household-level and are not scaled at the first death (as for
debts); a home with `yod = Y` pays its last property tax in `Y - 1`; with a move, split the rows at
the move year.

### 2. Cash flow and reporting (~40 lines)

- `_add_net_cash_flow`: `rhs -= self.housing_costs_n[n]`, next to the debt payments.
- The post-solve balance check (`plan.py:5386`), the outflow dictionaries (`plan.py:1015-1088`), the
  sources for the plots (`"housing"` next to `"debt pmts"`, `plan.py:7003`), the Cash Flow sheet and
  one Summary line (total housing costs, today's and nominal $).
- Net spending `g_n` then means non-housing spending, as it already excludes debt payments, so
  `maxSpending` results are comparable between rent and buy.

Key test: a plan with a `Housing` sheet gives the same objective, to solver tolerance, as the same
plan with those amounts entered as negative big-ticket items.

### 3. HFP read/write and the UI round trip (~60 lines)

- `hfp_io.py`: `_housingItems`, `_housingTypes`, read and write like the other two sheets;
  `houseLists["Housing"]`. A workbook without the sheet loads as before.
- `ui/owlbridge.py:1405` rebuilds `plan.houseLists` with only `Debts` and `Fixed Assets`, so as written
  it would drop `Housing`. Carry it through. A table editor on the Financial Profile page, copied from
  the Debts one, is optional here; the UI keeping the sheet from the file is enough, as the fork does
  for moves.

### 4. NJ property tax deduction in the state LP (~60 lines)

- `taxes_state.toml`, NJ_MFJ and NJ_Single, a new optional field with its sources:
  `property_tax_deduction = { cap = 15000, rent_share = 18, indexed = false }`.
- `StateTaxParams`: `ptd_cap_n`, `ptd_rent_share_n` (0 in years whose state has none).
- Plan, before the solve: `st_ptd_n = min(ptd_cap_n, housing_property_tax_n + ptd_rent_share_n *
  housing_rent_n)`, per year.
- LP: a variable `st_pt` (one per year, only when some `st_ptd_n > 0`), bounds `[0, st_ptd_n]` in
  `_add_state_tax_bounds`, coefficient +1 in the `state_taxable_income` row, the same position as
  `st_e`. It is **not** added to the exclusion's total income `L` in `_add_state_tiered_exclusion`,
  because line 41 comes after line 39. No binaries, so `localsearch.FAMILIES` does not change.
- Not modeled, documented: the $50 credit (worth at most $50 in a year where the deduction is
  worth less), the main-home and multi-unit rules (rows are assumed to be the main home), part-year
  amounts.
- Taxes sheet / explanation: show the deduction where it is nonzero, as for recapture.

### 5. Tests

- `housing.py`: growth (real rate with `gamma_n`), `year`/`end` bounds, `end <= 0`, `active`.
- Step 2's equivalence test (housing sheet = negative big-ticket items).
- NJ deduction: owner with $20,000 property tax (deduction $15,000), tenant with $30,000 rent
  ($5,400), state tax equal to a hand calculation; NY plan unchanged by the same rows; NY to NJ move:
  deduction only in NJ years; a year near an exclusion ceiling keeps the same tier with and without
  the deduction.
- HFP write-read round trip with a `Housing` sheet; UI sync keeps it.
- The constraint-replay guard (`test_replayed_rows_match_a_fresh_build_...`) extended with a
  housing row in NJ.
- One NJ + housing case under `breakpointMethod="local-search"`, to check that it runs.

### 6. Scenarios and templates (`fork-notes/phase0/`)

- `gen_hfp_us.py` writes an empty `Housing` sheet; the template comment on housing drops the
  "negative big-ticket items" advice.
- Scenario 5 (rent vs buy) written out: rent = one `rent` row; buy = big-ticket items (down payment
  and closing costs) + `Debts` (mortgage) + `Fixed Assets` (`residence`, `year` = the January after
  the purchase, `basis`, `rate`, `yod`, `commission`) + `Housing` rows (property tax, insurance,
  maintenance). One HFP workbook per housing variant.
- How to read it: home equity cannot be spent in Owl, so under `maxSpending` with `bequest = 0` the
  buy variant leaves the house unspent. Compare with `maxBequest` at the same `netSpending` and read
  `final_bequest_today` (counts the house, net of remaining debt). Second view: `maxSpending` with the
  residence sold in a chosen year and rent after it. Loop noise rules from Phase 1 apply: local
  search and the exact-LP cross-check for each variant.

### 7. Measure, then upstream

- Stakes on the Phase 1 synthetic couple (`fork-notes/model-review/nj_stakes.py` style): NJ owner and
  tenant with and without the deduction; NY vs NJ owner at one home price. Record in PROGRESS.md.
- Draft one design issue, `fork-notes/issue-housing.md`: the `Housing` sheet (generic; the
  equivalence test as evidence), with the NJ deduction as the first state rule that uses it (pure LP,
  per year). Patch rebuilt and verified on stock `dev`, as for #158. The user files it.

## Out of scope for Phase 2

- **Federal itemized deductions** (SALT, mortgage interest): Phase 3. Recalled, not verified this
  session: the OBBBA SALT cap is $40,000 for 2025, rising 1%/yr through 2029, phased down above $500k
  MAGI, and back to $10,000 from 2030. If so, itemizing could beat the standard deduction only for a
  NY/NJ owner in 2026-2029. Phase 3 needs mortgage interest per year, which `debts.py` can give
  (payment minus the change in balance), and NY's own itemized deduction.
- NJ ANCHOR, Senior Freeze and Stay NJ: separate relief programs (the 1040i lists them only as
  hotline topics). Amounts and income limits not checked; for now, enter an expected benefit as a
  positive big-ticket item.
- NY STAR and senior exemptions: enter the property tax net of them.
- Reverse mortgages, spending home equity, choosing rent vs buy or the sale year inside the LP.

## Decisions (agreed by the user 2026-10-07: all three as recommended)

1. A new `Housing` sheet (recommended) rather than more big-ticket cells or a property-tax column on
   `Fixed Assets` (which would change an upstream sheet and leave rent nowhere).
2. The rent-vs-buy reading: `maxBequest` at fixed `netSpending`, comparing `final_bequest_today`
   (recommended), with `maxSpending` plus a planned sale as the second view.
3. The $50 NJ credit left out (recommended) rather than a loop rule that picks credit or deduction.
