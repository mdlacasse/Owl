### Version 2026.9.2

#### New: Conversion Regret page

A new page under *Stress Tests* prices the cost of committing to a first-year Roth conversion
before knowing what markets will do. Each historical scenario is solved with perfect foresight,
then re-solved with the first year pinned at each amount on a grid; the gap between them is the
regret of that commitment. One graph carries both halves of the question: the shape of the curve
is the risk of committing wrongly, and the right-hand axis restates it as a share of what
converting is worth at all. Regret is measured in whatever the case optimizes, so the page follows
the objective set on the *Goals* page.

The grid is sized from the scenarios themselves, and the page reports only what the run can
resolve: it declines to name a best commitment when the curve is flat within its own numerical
floor, reports a minimum on the last grid point as a lower bound, and gives a commit band rather
than a single amount, that band being far more stable than the point estimate.

#### New: a shared computing budget for every multi-solve page

Every page under *Stress Tests* costs the same thing — full-horizon optimizations — but each one
policed itself, or didn't: Monte Carlo accepted 10,000 trials silently, and *Spending vs Bequest*
re-solved the whole scenario set once per bequest level with nothing capping the level count.

They now share one model. Each page declares its cost, a caption under the **Run** button states
it along with a duration estimated from that case's own measured solve time, and the button is
disabled when a run exceeds what the deployment allows. The Community Cloud permits 500
optimizations or two minutes per run, whichever binds first; self-hosted installations are
unlimited, and `OWL_UNCAPPED=1` lifts the cap for testing.

#### Fixed: re-stating account balances no longer re-dates them to today

`setAccountBalances` takes a `startDate` — the date the balances are known, from which they are
back projected to January 1st. An *omitted* `startDate` meant "today" rather than "leave it
alone", so calling the setter a second time silently re-dated balances that had already been
dated, truncating the plan's first year to whatever remained of the calendar year. On one example
run in August, `yearFracLeft` fell from 1.00 to 0.34 and the final bequest moved by 23%.

Omitting the argument now keeps the date the plan already carries, falling back to today only on
a plan that has none. Passing `None`, `"today"` or a date behaves exactly as before. This also
fixes `setHSA`, which re-states the other balances internally.

#### Fixed: the HFP workbook download returned an error page

Downloading the HFP workbook produced a file named after a long string of digits, ending in
`.xlsx.txt` and containing `File not found`. The button's click handler called `st.rerun()`, which
aborts the run while the browser is still fetching the file it had just registered; Streamlit then
collected the orphaned media file and the request landed on a 404.

#### Changed: a plan that is not ready to solve says what is missing

Readiness checks are collected in `Plan._preflight()` and applied through the `_checkConfiguration`
decorator. Account balances are newly among them: without them the plan died with a bare
`AttributeError` deep in matrix assembly. The decorator now also guards the six multi-scenario
runners, where a misconfigured plan previously failed inside a worker thread after the pool had
been spawned.

### Version 2026.8.29

#### Changed: Roth conversion overrides are now a checkbox, not a negative number

The `Roth conv` column of the HFP workbook was doing three jobs at once: recording
conversions already performed, carrying an amount to pin, and encoding *which* of those
two it meant through the **sign** of the number. That made `0` mean "let Owl optimize
this year" rather than "convert nothing" — the opposite of what anyone typing a zero
expects — and it forced two workarounds. An absent column could not be told apart from a
column of zeros, so Owl had to refuse to run; and because `0` could not say
"unspecified", a global `useRothConvOverrides` toggle was needed to declare that the
column held instructions at all.

The column now does one job: **Roth conversion amounts in dollars, never negative**. On
the five lead-in rows they are conversions you have made; on plan years, conversions you
are proposing. A new optional boolean column, **`Roth conv fixed`**, says which of those
proposals bind. Ticked, the conversion is held at exactly the amount beside it, bypassing
the annual cap and the start and stop years. Unticked — the default, and what an absent
column means — Owl optimizes that year and the amount is documentation only.

Three things fall out of the separation. `0` means zero: a ticked year with an amount of
`0` converts nothing. Un-ticking a year keeps its figure in the sheet, which is what
flipping the sign used to be for. And an absent column is now unambiguous, so the refusal
and the toggle are both gone.

**This is a breaking change.** A negative `Roth conv` entry is now an error naming the new
column, and the `useRothConvOverrides` solver option has been removed, along with the
`use_roth_conv_overrides` parameter of the MCP tools. In the MCP `roth_conversions` list,
membership is what pins a year: give an amount of `0` where you used to give `-1`. The
shipped example workbooks and `HFP_template.xlsx` carry the new column.

#### Changed: the Wages and Contributions table is now two tables

In the workbook it remains one sheet per person; in the user interface it is shown as the
five lead-in years and then the plan years. This is what lets `Roth conv fixed` be disabled
on the past rows, where those conversions have already happened and the flag means nothing:
Streamlit can only disable whole columns, so the only way to disable a column on some rows
is to give those rows a table of their own.

Every column stays visible and editable on the past table. Workbooks get reused year over
year and the past wage and contribution figures are the record you extrapolate the next
year's from, even where the planner itself does not read them.

#### Added: `stopRothConversions`

The mirror of `startRothConversions`: no Roth conversions from the given year onward. The
two together bound conversions to a window, so "convert until Medicare starts, then stop"
is one number rather than a pinned zero on every remaining year. Exposed in the UI beside
the start year, and to the MCP tools as `stop_roth_year`.

#### Added: an HFP workbook download on the Financial Profile page

**Owl** adds any recognized column your workbook is missing and reads it as zero. It said
so, then told you to add the column yourself — but by then the column is already in the
table in front of you, and the only thing left to do is keep it. The notice now points at
a *Download HFP workbook* button at the foot of the same page, below every table the
workbook holds: the *Wages and Contributions* sheets, *Debts*, and *Fixed Assets*.

The existing download on the **Reports** page could not serve here: it is gated behind a
successful solve, which is no use to someone who has just loaded a workbook, and no use at
all if the case turns out to be infeasible. Building the workbook needs only the tables, so
this one is available as soon as a case has a plan.

Both pages now also note that the browser, not **Owl**, decides where a downloaded file
lands, and name the preference that makes it ask each time.

#### Bugfix: a case file could record a workbook name that cannot exist

The UI appends `" *"` to the workbook name to mark it edited since it was loaded, and uses
`"edited values"` when the tables were typed with no file behind them. Neither is a file
name, but both reached the case file — saving one produced
`HFP_file_name = "HFP_jack+jill.xlsx *"`, a reference that can never be reloaded.

The name is now normalized where it is written and where it is read, so a case file always
records something real, and one that already carries a stale marker is repaired the next
time it is loaded. A trailing marker only: a workbook whose own name contains `" *"` is
left alone.

#### Bugfix: saving an HFP discarded past wages

`saveHFP` rebuilds the time lists from the plan's arrays whenever it judges the stored ones
stale, and the staleness check compared `anticipated wages`, `other inc`, `net inv`, `QCD`
and `big-ticket items` on the five lead-in rows. The arrays are sized for plan years and
carry nothing for the past, so the rebuild has zeros there and any real past figure read as
"stale" — after which the save wrote those zeros over it. Loading `Case_alex+jamie` and
saving it lost \$215,000 of Alex's recorded wage history.

The check now compares only what the arrays actually represent: those five columns on plan
years, contributions and `Roth conv` everywhere. A plan-year divergence still reports stale,
which is what the check is for.

#### Bugfix: stress-test results did not say what was being held fixed

A histogram of outcomes over historical scenarios or Monte Carlo trials only means
something next to the quantity that was *not* free to move. Maximizing net spending holds
the savings bequest at its target; maximizing bequest holds net spending at its target.
Neither appeared anywhere in the results, so a range of spending figures could not be read
without going back to the **Goals** page to recall which bequest produced it.

The summary beside the histogram on the **Historical Range** and **Monte Carlo** pages now
opens with that value — `Savings bequest constraint` when maximizing spending, `Net spending
constraint` when maximizing bequest — in today's dollars, like the statistics below it, and
padded to the same column so every amount lines up.

The **Spending Optimization** page runs the same maximization over every scenario, so its
summary now opens with the same `Savings bequest constraint` line. The committed spending it
reports is the amount sustainable *while leaving that estate*, and the figure moves with the
bequest target on the **Goals** page.

#### Bugfix: stress-test log messages did not say which scenario they came from

Some stress tests solve their scenarios in parallel, and every worker writes to the one log the
**Logs** page shows. Nothing in a line said which scenario had produced it, so a message
about a slow solve or a rate assumption could not be traced back to the year or trial it
belonged to, and the log read as one interleaved stream. Two workers could also land in the
middle of each other, splitting a line in half.

A line written by a worker now carries the scenario between its location and its message —
the historical start year, or `#0`, `#1`, … for Monte Carlo trials:

```
2026-08-29 23:28:19 | INFO | plan:_build_sc_loop_policy:4213 | 1960 | Using relTol=5.0e-05, ...
```

This covers the **Spending Optimization** and **Spending vs Bequest** pages, and the
stochastic tools of the AI assistant, which are the runs that solve scenarios in parallel.
Lines are also written whole, so they can no longer be cut in half by another worker.
Anything logged outside such a run keeps the format it had.

#### Bugfix: the historical bar chart was always labelled "bequest"

The heading over the chart of results by historical start year on the **Historical Range**
page read *Optimal bequest by historical start year* whatever was being maximized. It now
follows the objective, and says *net spending* when that is what the bars are.

#### Docs: the UI manual audited against the app

The **Documentation** page is written by hand and no test checks it, so it drifts. A pass
over it brought it back in line: the *Qualified Medical Expenses* and *ACA Marketplace
(Pre-65)* fields are now described, a *When there are no results* section explains the case
where a plan is achievable and the solver is what gave up, and the MCP server section says
what an assistant can actually drive.

Smaller corrections along the way: the AI page advertised 16 tools when there are 18 and did
not mention `run_year1_robustness`; the fixed-rate help pointed at Morningstar's 2025 return
forecast, now the 2026 one; and a *Settings* link pointed at an anchor that does not exist.

#### Docs: bubble help on the Wages and Contributions columns

The *Debts* and *Fixed Assets* tables explain every column in a tooltip; the timetables
above them explained none, leaving fourteen abbreviated headers — *net inv*, *taxable ctrb*,
*QCD* — to be resolved on the **Documentation** page, in another tab, while you were typing
into the table.

Each column now carries a one-line description where you are working: what belongs in it,
in which dollars, and the rule worth knowing before you fill it in — that *anticipated
wages* is net of every contribution column, that a ticked *Roth conv fixed* with an amount
of `0` means no conversion that year, that a *QCD* never reaches your budget. The
*big-ticket items* tooltip says that its sign is the difference between money received and
money spent. The long form stays on the **Documentation** page.

The five lead-in years get their own wording for the two columns that mean something else
there: a past *Roth conv* is a conversion you have already performed rather than one you
are proposing, and *Roth conv fixed* does not apply to it.

#### Maintenance: Updated dependencies

`anthropic` 1.0.0 → 1.2.0, `ipython` 9.16.1 → 9.17.0, `jupyter-client` 8.9.1 → 8.10.0,
`jupyter-server` 2.20.0 → 2.21.0, `kiwisolver` 1.5.0 → 1.5.1, `platformdirs` 4.11.4 →
4.11.5, `pydantic` 2.13.4 → 2.13.5, `pydantic-core` 2.46.4 → 2.46.5, `wcwidth` 0.8.2 →
0.8.3, `websocket-client` 1.9.0 → 1.9.1.

### Version 2026.8.26

#### Bugfix: a seeded MCP stochastic tool did not repeat itself
`run_stochastic`, `run_longevity_stochastic`, `run_year1_robustness` and
`run_spending_bequest_frontier` document a `seed`, but none passed it to the plan
builder. Seeding afterwards is too late for a rate model that is *fitted* rather than
sampled: `gmm` fits its mixture by EM from a random start while `setRates()` runs, and
a later reseed only affects sampling. Under `gmm`, `seed=42` gave a different answer
every call — spending at the top of the frontier ranged over 3.8x on one household.
Sampled methods such as `lognormal` were unaffected.

`run_longevity_stochastic` also sampled lifespans unseeded, and solved its gating plan
before any seeding at all — which made it fail outright when that unseeded draw
happened to defeat the solver.

#### Added: `make outdated`
Lists the packages `make update` would upgrade, without changing anything.

#### Maintenance: Updated dependencies
`click` 8.4.2 → 8.5.0, `cryptography` 50.0.0 → 50.0.1, `mcp` and `mcp-types` 2.0.0 →
2.1.1, `platformdirs` 4.11.3 → 4.11.4, `plotly` 6.9.0 → 7.0.0, `scipy` 1.18.0 → 1.18.1.

### Version 2026.8.21

#### Added: Qualified Charitable Distributions - Issue #137
A QCD sends money from a tax-deferred account straight to a charity. It is not the
same as withdrawing the money and donating it, and the difference is worth real money
to a charitably-inclined retiree with a large IRA. Enter amounts in the new `QCD`
column of the HFP workbook, per person and per year.

Owl models the four properties that make it distinct. The amount is excluded from AGI,
so it is invisible to federal and state income tax, to the taxability of Social Security,
and to the MAGI behind IRMAA and the NII tax — a stronger benefit than a charitable
deduction, which most retirees cannot use because they take the standard deduction. It
counts toward the RMD dollar-for-dollar, lowering the taxable distribution the plan is
forced to take. It leaves the tax-deferred balance, which shrinks later RMDs too. And it
never reaches the household budget, so it funds no spending.

Age 70½ and the annual per-person limit (\$108,000 in 2025, \$115,000 in 2026) are
enforced as errors rather than silent adjustments. IRS publishes the limit a year at a
time, so later years carry the last published figure forward at a fixed 3.0% — the
geometric mean of CPI across Owl's full 1928–2025 rate history. The rate is deliberately
a constant and not the scenario's own inflation: the cap validates user input, and a
scenario-dependent bound would accept an entry on one Monte Carlo path and reject it on
the next.

`Case_jordan+taylor-qcd` is the worked example: `Case_jordan+taylor` with a giving
schedule added and nothing else changed, so a comparison isolates one variable. Jordan
and Taylor give \$1.17M (today's dollars) between 2029 and the end of the plan. Funded
from after-tax cash they end with \$1,057,269; routed through QCDs, \$1,205,027 — about
\$148,000 more estate, from \$220,000 less in tax and Medicare premiums. \$1.30M of the
giving satisfies RMDs outright. The freed ordinary-income headroom is not wasted: the
optimizer converts it to Roth dollar-for-dollar, so taxable income barely moves and the
benefit lands in the estate rather than in a smaller tax bill.

Limitations, all stated in the documentation. QCDs must be paid from an IRA, not directly
from a 401(k)/403(b), and Owl aggregates both into one tax-deferred account so it cannot
tell them apart. That is a planning step rather than a real obstacle: rolling the employer
plan over to an IRA first makes the money eligible, and the rollover is itself a non-event
in the model, since both balances already live in the same account. The anti-abuse offset
for deductible IRA contributions after 70½ is not applied, and the one-time
split-interest-entity QCD is not modeled.

#### Changed: HFP person sheets no longer require every column
Version 2026.03.26 made all person-sheet columns mandatory. That is reversed for
robustness: only `year` is required now, and any other recognized column may be omitted
and is read as zero for every year, with a message naming the columns that were absent.
List the columns your household actually uses.

Strictness was worth having for one reason — it caught a misspelled header, because the
misspelling was dropped and the properly named column then came up missing. That
protection no longer depends on it. A header differing from a recognized one only by
capitalization, spacing, or punctuation is now reported as a typo and names the intended
spelling. Matching is on exact equality after folding, never fuzzy, so genuine helper and
calculated columns are still dropped silently as documented.

One column is exempt. Under `useRothConvOverrides`, `Roth conv` carries meaning rather
than dollars: `0` means "leave this year unconstrained". An absent column would read as
"no year is pinned" — the one case where absence is ambiguous rather than simply zero — so
Owl refuses to run instead of guessing. With the option off it is optional like the rest.

### Version 2026.8.19

#### Changed: `Case_cameron` now describes a household that can afford to live
The example carried a Social Security benefit of \$200/month, which implies almost no covered
earnings record and does not belong with \$119,000 of savings. It left the plan spending
\$7,192/yr in today's dollars — below the poverty guideline for one person, and about three
times the Medicare premium the plan pays in its first year.

Cameron now has a lifetime low-to-middle earner's record: a PIA of \$1,250/month, worth about
\$1,550/month deferred to 70. The state is New York rather than California and the bequest
target is \$20,000 rather than \$40,000. Spending rises to \$18,996/yr.

What the case exists to cover is unchanged. The benefit stays below the threshold where Social
Security becomes taxable, so the plan still owes no federal, state or capital-gains tax in any
of its 27 years, still solves as a pure linear program, and still exercises the degeneracy that
a zero marginal rate creates. New York widens that: its retirement income exclusion is another
variable free to move when there is no income to shelter.

#### Maintenance: Updated dependecies (again) to silence GitHub's dependabot.
Upgrade to Streamlit 1.62.

### Version 2026.8.18

#### Maintenance: Updated dependecies to silence GitHub's dependabot.

#### Removed: `fixedSpending`, which could charge more than the top marginal tax rate
Issue #140. Set below what a plan can afford, it produced ordinary tax above the top statutory
rate — 46.7% on \$292,001 in the reporter's worst year, against about \$65,300 by hand.

It pinned `g(0)`, and at the default `spendingSlack` of zero the profile rows tie every `g(n)`
to it, fixing the whole spending vector. The `maxSpending` objective is built only from `g(n)`,
so it became *constant* over the feasible set. The bracket-fill variables `f_tn` are a
relaxation of the progressive schedule, tight only because the objective pushes income into the
cheapest brackets; with nothing left to push, the solver could fill the 37% bracket while lower
ones sat empty, at no cost to a constant objective. Raising `spendingSlack` does not help — the
band's ceiling is itself proportional to the pinned `g(0)` — and `epsilon` was not implicated.

Rejected rather than ignored, at config load and in `Plan.solve()`, since a plan that silently
dropped it would answer a different question than the case file asks. Replaced by the trade-off
below.

#### New: the spending-vs-bequest trade-off
Answers *what does leaving an estate cost me in spending?* Sweeps the `bequest` floor under
`maxSpending`: every point is an ordinary solve, and because the floor constrains the estate
rather than spending, the objective keeps its gradient.

In `historical` and `mc` modes each level is also solved across the whole scenario ensemble,
giving a surface *S(B, p)*: down a column, spending versus bequest at fixed confidence, the fan
across success rates being sequence-of-returns risk; across a row, the spending/success curve of
`run_stochastic_spending`, which it reuses rather than reimplements.

The swept bequest is the savings accounts after the heirs' tax, net of debt. Assets still held
at the end of the plan pass outside those accounts, so they are reported separately and added
into a total estate; set by the asset table rather than the floor, that figure is identical at
every level. Stochastic rows also carry the count of scenarios that could not reach the level,
which is what drags the high-confidence curves down. The largest reachable estate is a bracket,
not a value: a sweep only shows it lies between the highest level that solved and the lowest
that did not.

Available as `Plan.runSpendingBequestFrontier()` and `owlplanner.run_spending_bequest_frontier()`
with a `summarize_*` companion, the **Spending vs Bequest** page, `owlcli frontier`, and the
`run_spending_bequest_frontier` MCP tool (eighteen tools now). The `bequest_floor` shadow price
is available via `with_duals`, off by default.

### Version 2026.8.16

#### Bugfix: the reported Social Security taxability was not the one the plan was charged
The taxable-income row carries `Psi_n * zetaBar` as a parameter, so a solved plan satisfies
`e_n + G_n = (non-SS ordinary income) + Psi_n * zetaBar_n`. The self-consistent loop advances
`Psi_n` after every solve, for the *next* iteration's constraints. `M_n`, `J_n` and `ACA_n` are
rolled back afterwards to the values the final LP embedded; `Psi_n` was not, so it came back one
step ahead of the figure behind the numbers — two steps when the post-loop LTCG consistency pass
ran, since that advances it again.

The same step landed in `MAGI_aca_n`, which is defined to be independent of `Psi_n`:
`MAGI_n` already carries the taxable share, and `MAGI_aca_n = MAGI_n + (1 - Psi_n) * zetaBar`
cancels it — but only when both use the same `Psi_n`. On `Case_chris+pat` the reported taxable
benefit was out by up to \$13,558 in a year and \$207,584 over the horizon. Plans that converge
monotonically were never affected: they settle, so there is no step to lose.

Nothing about the money changes — the tax charged was always consistent with the `Psi_n` the LP
was built with. What changes is that the plan now reports that figure rather than a later one.

#### Bugfix: taxable Social Security could be reported in a year that owed none
With `withSSTaxability = "optimize"`, nothing selected between the two `z_0` branches in a year
where the benefit's taxability costs nothing, and the branch that sets `z_0 = 1` forces the
excess-provisional-income variables *up* to their caps rather than down to the IRS values. A
retiree whose provisional income sat at \$5k-\$22k, against a \$25,000 threshold, could have
half or 85% of the benefit reported as taxable where the correct answer is none.

The objective already carries small preferences that break ties like this, but at `EPSILON = 1e-8`
this one was invisible: against a few thousand dollars of benefit it moves the objective by about
1e-5, below the solver's own optimality tolerance, so branch-and-bound stopped at whichever
incumbent it found first. `MIP_TIEBREAK`, sized for a gap rather than for the simplex, resolves it.
The value is far below any real cost — a taxable dollar of benefit is worth at least the lowest
bracket rate — and the objective is identical across two orders of magnitude around it.

A case that settles on a cycle can still report a wrong share, because it is answered from a
best-of-cycle iterate; raising the preference enough to pin that begins to move the objective
instead, so it is left as it is.

### Version 2026.8.15

#### Bugfix: taxable Social Security was computed from the wrong provisional income
`withSSTaxability = "optimize"` builds provisional income as a row of raw income components —
withdrawals, conversions, dividends, realized gains, wages, pension, plus half the benefit. Those
components already are non-Social-Security ordinary income plus capital gains, which is the whole
of what the formulation asks for: Eq. (PI) states that taxable Social Security does not appear in
provisional income, and neither does the standard exemption. The row added the exemption `e_n` and
subtracted `t^σ_n` on top of them anyway, so the IRS piecewise formula was applied to
`Π_n + e_n − t^σ_n`.

This is the same family as the 2026.8.13 exemption bug, in the third row that builds an income
figure from components; that fix corrected IRMAA and ACA and left this one standing.

The error is invisible wherever the 85% cap binds, since the answer is then `0.85·ζ̄` for any
provisional income at all — which is why bounds tests and a cap-binding test passed while the
definition was wrong. It bites on the taxability ramp, and its sign follows `e_n − t^σ_n`: the
figure runs high while the exemption exceeds taxable benefits, and low once benefits are largely
taxable, which is the case that costs money. On `Case_dana` under `maxBequest` at the 1966
sequence, \$153,488 of taxable Social Security went untaxed across 27 years, up to \$16,981 in a
single year, and the bequest came back \$462,211 against a corrected \$452,598.

Loop mode never built the row and is unaffected, as are all default solves — the option is off by
default, and no pinned case objective moves.

The regression test asserts the identity the formulation states, that the reported taxable benefit
is what the IRS formula returns for the plan's own provisional income, on a plan whose Social
Security years sit on the ramp. It refuses to pass on a plan where every year is at the cap, since
there the identity holds no matter what the row computes.

#### Added: `plan.medicare_n`
Medicare premiums land in a different array depending on how they were solved:
`withMedicare = "optimize"` puts them in the LP variable `m_n` and leaves `M_n` at zero, loop mode
does the reverse. Reading either one alone therefore reports the full premium on one path and zero
on the other. `medicare_n` is the total, and every reporting path — summaries, cash-flow mixes,
worksheets, the Excel export, the CLI, the tax plot — now reads it instead of adding the two
arrays by hand.

### Version 2026.8.14

#### Deprecated: `withSCLoop`
The option promised speed in exchange for precision. What it did was leave Medicare out of the
budget constraint while still reporting the premiums, so the plan spent money it would have owed:
`Case_dana` came back 3% high and `Case_cameron` 34% high, the same ~\$2,435 of unbudgeted premium
in both.

There is nothing it could legitimately switch off. Even with every tax feature set to `"optimize"`,
where the MILP is meant to absorb the nonlinearities, the loop still resolves two quantities that
have no formulation inside the optimization: the standard exemption's OBBBA 65+ phaseout, which is
computed from MAGI, and the cost-basis gain fractions, which depend on the withdrawals themselves.
Turning the loop off does not trade accuracy for speed; it stops the plan converging.

Where a shorter loop is genuinely wanted, `maxIter` already does it coherently — `maxIter = 2`
reproduces the full-loop answer exactly on the cases above, at the same speed, with Medicare in the
budget throughout.

A case file that still sets the option loads, reports it as deprecated, and solves properly. Two
consequences worth noting: a solved plan now always carries a real convergence verdict, where
before this mode left it `undefined` — which the historical sweeps counted as a solve needing an
error bar — and the Medicare cost is no longer simultaneously absent from the budget and present in
the report.

#### Changed: the expert MILP toggles say what they do
"Optimize Medicare", "Optimize ACA", "Optimize LTCG brackets" and "Optimize NIIT" implied that the
alternative does not optimize those things. It does — every one of them is modeled either way, and
the toggle chooses how. They now read "Solve … with MILP", and their help text says the bracket is
chosen inside the optimization rather than by iteration, which is exact at a bracket edge and
slower.

### Version 2026.8.13

#### Bugfix: IRMAA and ACA brackets were selected on MAGI plus the standard exemption
MAGI is defined once, in the formulation: `G_n + Q_n + e_n`, where `G_n` is taxable ordinary
income after the standard exemption, so adding `e_n` back recovers AGI. The rows that split MAGI
into IRMAA and ACA bracket portions built it from raw income components instead — withdrawals,
conversions, dividends, realized gains, taxable Social Security, wages, pension — which already
include the exemption, and then subtracted `e_n` as well. The figure the optimizer worked from
came out one exemption too high.

The consequence fell on `withMedicare = "optimize"` and `withACA = "optimize"`, whose purpose is
to fill a bracket exactly. On a single retiree the IRMAA constraint was binding in all thirteen
Medicare years while the true MAGI sat \$12,432 to \$21,859 under the tier ceiling, so that much
Roth conversion capacity went unused each year on the belief the year was already at the edge.
Objectives improve accordingly, by a few hundred dollars of annual spending on the plans measured.
The first two plan years were always right, since they use the MAGI supplied through
`previousMAGIs`, and loop mode was never affected because it reads the reported MAGI directly.

A regression test now asserts the identity the formulation states — that the bracket portions sum
to the reported MAGI — rather than checking a premium, since a bracket only moves when the error
happens to straddle a threshold and a premium check would have passed for years.

`Case_jack+jill` moves 102,697 to 102,515 despite the correction relaxing its brackets: that case
converges oscillatory, so the loop settles on a best-of-cycle iterate and the change shifted which
one. Plans that converge monotonically all improved.

### Version 2026.8.12

#### Bugfix: a pinned rate seed now reproduces the same series on any machine
Rate models that draw correlated returns used `Generator.multivariate_normal`, which
factorizes the covariance by SVD unless told otherwise. An SVD is only determined up to
conventions that differ between LAPACK builds, so macOS and Linux drew different numbers from
the same seed — not by a sign, but entirely. `rate_seed` therefore reproduced a series only on
the machine that produced it, and `Case_chris+pat` solved 17% apart across platforms.

The draw now goes through a Cholesky factor, which is unique, so a seeded series is the same
everywhere. This is what `vector_ar` and `garch_dcc` already did by hand; it now applies to
`gaussian`, `historical_gaussian`, `lognormal`, `historical_lognormal`, `historical_copula`,
`gmm` and `hmm`. `historical_bootstrap` resamples whole years and was never affected. A
covariance that is not positive definite cannot be factorized this way, so those cases fall
back to the previous behavior and warn that the seed will not carry to another machine.

Numbers drawn from these models change, since the draw itself changes: `Case_chris+pat` moves
about 3%. Results from `historical` and `historical_average` are unaffected — they read
recorded returns and involve no draw — as are historical-window analyses, which override the
case's rate method entirely.

### Version 2026.8.11

#### Change: transaction exclusions are restored after the solve, not constrained during it
Two properties keep a plan readable: a Roth conversion and a tax-free withdrawal do not fall in
the same year, and a surplus is not banked in a year that also withdraws from a taxable or
tax-free account. Both were enforced with big-M binary variables, which are removed. Across every
shipped example under both solvers, the constrained and unconstrained optima are the same.

Both properties are now re-established on the solved plan. A same-year conversion and tax-free
withdrawal are rewritten as a larger tax-deferred withdrawal, leaving balances, income and net
cash unchanged. A surplus is reported net of the deposit returning to the account it was drawn
from, which cancels on both sides of the cash flow balance. Any overlap left is re-examined by a
re-solve that cannot change spending, the terminal balances or the conversion schedule.

Nothing is rewritten below age 59½, where a conversion ladder needs that overlap. Where the
substitution does not hold — non-zero `oppCostX`, `withdrawalOrder = "taxable_first"`, or one
spouse converting while the other withdraws — the overlap is reported rather than removed.

These were the only binary variables a plan carried by default, so unless an `"optimize"` tax mode
is on, Owl now solves a pure linear program: no branch-and-bound, no optimality gap, no time
limit. Solve times drop sharply for plans that owe no tax in any year, where the objective cannot
distinguish one account from another and the search had nothing to narrow it; the new `Case_cameron`
went from 577 seconds to 0.05. Two example cases that previously disagreed between HiGHS and MOSEK
now agree exactly.

#### New: `Case_cameron`, a modest-portfolio example
A single 66-year-old renting in California, about \$119,000 of savings, no pension, \$200/month at
70. Every other shipped example owes federal tax; this one does not, which is the regime that was
slowest to solve. Included as a worked small-portfolio scenario and a regression case.

#### Bugfix: withdrawal-ordering gates could be bypassed by a few hundred dollars
The `taxable_first` order is enforced by gates that open once an account is exhausted. They used a
generic big-M of 5×10⁷, and a solver's integer tolerance allows slack in proportion to it — enough
for several hundred dollars to remain in an account the plan had declared empty, letting
tax-deferred withdrawals exceed the RMD a year early. The gates now use a bound computed from the
portfolio, capped by the previous constant so the formulation can only tighten.

The other big-M families were measured rather than changed: nothing leaks at the shipped defaults,
but raising `bigMamo` by two orders of magnitude misplaced \$34k of MAGI on a Medicare-optimize
plan, and by four, \$131k and a 1.5% inflated objective. Those options now carry a warning against
raising them.

#### Bugfix: MOSEK failed on problems with no integer variables
`_mosekSolve` read the integer solution slot unconditionally, which is only populated when integer
variables exist. Previously masked by the exclusion binaries; a default plan is now a pure LP, and
MOSEK is the default solver when licensed.

#### Deprecated: `amoConstraints`, `amoRoth`, `amoSurplus`
These three options no longer do anything. A case file saved before this release still loads and
solves, with each option reported in the plan log as deprecated and ignored. They are removed from
the shipped examples, the case-file schema, and the Run Options page. `bigMamo` is unaffected and
still sets the big-M shared by the remaining at-most-one families.

#### Note on reported values
Several example cases shift slightly, all attributable to which fixed point the self-consistent
loop settles on. `Case_john+sally` gains about 1.6% of bequest at unchanged spending. The 1966
maxBequest reference for `Case_dana` used by the conversion-regret sweep moves more: the previous
value came from a solve that exhausted its iteration limit without converging, where the current
one converges on a detected cycle.

### Version 2026.8.10

#### New: survivor Social Security claiming age in the MCP tools
`ss_survivor_claim_age` is now a parameter on every MCP solve tool — `run_from_params`,
`save_case`, `compare_to_baseline`, `explain_results`, `run_stochastic`, `run_year1_robustness`,
`run_longevity_stochastic`, `run_historical`, and `run_monte_carlo` — accepting `"immediate"`
(default), `"FRA"`, or an age in 60–70. `save_case` persists it to the generated TOML only when
it differs from the default, and `compare_to_baseline` applies the same value to both sides,
since the survivor claiming date is a household input rather than one of the strategies under
comparison.

#### New: survivor Social Security claiming age
The date at which a surviving spouse claims the survivor benefit is now a setting rather than a
fixed assumption. `setSocialSecurity()` takes a `survivor_claim_age` argument, case files take
`social_security_survivor_claim_age` in `[fixed_income]`, and the Streamlit **Fixed Income** page
exposes it under *Advanced options* for married cases. Accepted values are `"immediate"` (the
default, and the previous behavior), `"FRA"` (the survivor's full retirement age), or an explicit
age in 60–70. A survivor benefit never starts before age 60 or before the first passing, and an
age beyond the survivor FRA is capped there since survivor benefits earn no delayed retirement
credits. Whenever one of those constraints overrides the requested age the plan log carries a
`WARNING` naming the age actually used and why; separately, a claiming age below the survivor
FRA is reported with the resulting permanent reduction, since that is easy to select without
intending it. The setting works in both the default self-consistent-loop mode and under
`withSSAges="optimize"`, and is re-resolved per scenario under stochastic longevity sampling —
it is a policy ("claim at the survivor's FRA"), not a fixed calendar date.

The default remains `"immediate"`, which reproduces the previous behavior, so no existing case
file changes its results on load.

#### Bugfix: survivor no longer forfeits their own Social Security benefit
Own, spousal, and survivor entitlements are now built as three separate streams and combined the
way SSA pays them — own plus excess spousal while both spouses are alive, and the greater of own
and survivor from the first death onward. Previously the survivor benefit was written over the
survivor's entire remaining horizon with a single one-shot comparison made in the year of death.
Three defects followed from that, all fixed here:

- A survivor who had not yet started their own benefit when their spouse died had it erased for
  life, because the comparison saw a zero own benefit and the assignment overwrote everything
  after it. For a survivor with the larger earnings record deferring to 70, this silently dropped
  roughly \$20k/year for the rest of the plan — and it happened regardless of the survivor's age
  at the first death, including well past their survivor FRA.
- A survivor whose own benefit won the one-shot comparison was never stepped up to the unreduced
  survivor benefit at their survivor FRA.
- A survivor under 60 at the first death began collecting immediately. The age-60 minimum was
  applied to the reduction factor but not to the start date.

Under `withSSAges="optimize"` the same overwrite drove the spousal/survivor parameter offset
sharply negative, feeding the LP a phantom income deduction for every candidate claiming age.
The offset is now the excess survivor amount and is non-negative by construction. When the
first-to-die's claiming age is not itself a decision variable — the common case, since that
spouse is usually already collecting — the survivor stream is folded directly into the
own-benefit table, making the post-death payout exact for every candidate claiming age instead
of approximated across self-consistent iterations.

Reference objective values for the example cases are unchanged: in every married example the
survivor is already collecting and past their survivor FRA when the first death occurs, which is
precisely the configuration the old code handled correctly.

### Version 2026.8.2

#### Removal: vestigial `tax_fraction` argument to `setSocialSecurity()`
`withSSTaxability` replaced `tax_fraction` as the way to pin the Social Security taxable
fraction, but the old argument was left in place and had since fallen out of sync with the code
that consumes it. It was validated against [0, 1] and recorded on the plan, and it suppressed
the self-consistent update of `Psi_n` — but never set the level, which fell back to the
hardcoded 0.85 default. Every value therefore behaved as 0.85, silently: `tax_fraction=0.0`
and `tax_fraction=1.0` produced bit-identical results. The argument is now removed; pass a
numeric `withSSTaxability` in the solver options instead, which does set the level. Two
regression tests were added covering `withSSTaxability=1.0` (previously untested, and
unreachable through the IRS formula, which caps at 85%) and asserting that distinct fractions
yield distinct solutions — the property whose absence hid the defect.

### Version 2026.7.29

#### Bugfix: Social Security and pension claiming ages snap to whole months
Claiming ages carry month precision (e.g. 62 years 1 month = 62 + 1/12 = 62.08333…). A value
that had round-tripped through a TOML case file as a truncated decimal (`62.083333`) was used
verbatim by `readConfig`, while the Streamlit UI (which enters ages as years + months) used the
exact `62 + 1/12`. The resulting sub-cent difference in the computed benefit stream could be
amplified by the mixed-integer program into dollar-level differences between a config-loaded plan
and a UI-built one. `setSocialSecurity` and `setPension` now snap claiming/commencement ages to
the nearest whole month (`round(age * 12) / 12`) on entry, so the API, the UI, and case files all
agree. A regression test was added in `tests/config/test_config_coverage.py`, and the reference
objective values for example cases with fractional claiming ages were updated accordingly.


### Version 2026.7.27

#### Maintenance: mcp update to v 2.x
Update MCP package to latest version. This change broke a few imports.

#### Maintenance: Update gitpython
Update gitpython due to vulnerability identified by GitHub bots.


### Version 2026.7.20

#### New: example case `devon`
`examples/Case_devon.toml` (+ `HFP_devon.xlsx`): the wealth-axis companion to `dana` — a
single Californian at the retirement threshold with the same balance sheet scaled four-fold,
≈\$4.75M of savings concentrated in a \$3.75M traditional IRA (\$600k taxable, \$400k Roth), a
near-maximum Social Security benefit (PIA \$4,000/month) at 70 from a career at the earnings
cap, RMDs at 75, and a \$1.6M bequest target beside a home left to heirs. Everything else —
single filer, California, fixed 60/40 allocation, uncapped conversions, `historical_average`
base rates — matches `dana`, so wealth is the only moving part: at this level the conversion
moves from the 12–22% brackets into 24–32–35%, straddles multiple Medicare IRMAA tiers,
engages the net investment income tax, and RMDs alone push income high enough that doing
nothing is expensive. Paired with `dana` for studying how the first-year conversion decision
scales with wealth; both cases are now selectable in the Streamlit UI's example-case list
(`ui/tomlexamples.py`).

#### New: commitment-regret sweep for the first-year Roth conversion
`run_conversion_regret_sweep` and `summarize_conversion_regret` (in `stresstests.py`, exported
from `owlplanner`) price the cost of committing to a fixed first-year Roth conversion. For each
historical (or supplied) scenario the tool pins the first-year conversion to each value on a
grid, lets every later year re-optimize with full knowledge of that scenario, and returns the
regret `R = V* − V(x)` against the clairvoyant optimum; where the self-consistent tax loop does
not settle cleanly, it also records the residual oscillation amplitude of each end (`v_star_osc`
for `V*`, `v_at_osc` for `V(x)`). The summary reports the dispersion of scenario-optimal
conversions, the valley (lowest-mean-regret commitment), the over- versus under-conversion
asymmetry at ±\$15k/\$30k/\$45k (under-conversion floored at zero, since a conversion cannot be
negative), infeasible-scenario counts, and the never-convert cost.

#### New: objective error bar for unsettled self-consistent solves
Every solve now tracks the amplitude of any residual oscillation in its objective when the
self-consistent tax loop cannot settle on a single fixed point — `plan.oscillationAbs` and
`oscillationRel`, in the units of the modified objective (today's dollars). It is exactly zero
when the loop converges within tolerance and nonzero only when a near-threshold bracket
ambiguity leaves the accepted objective sitting inside an oscillation band, so a genuinely
missing value would raise rather than silently read as "no uncertainty." The plan summary
(`export.py`, `build_summary_dic`) now reports it per solve as
`Objective error bar (…, today's $)` — half the peak-to-peak spread each way — beside the
convergence type. The regret sweep aggregates the same quantity across scenarios: because the
`V*` and `V(x)` ends oscillate independently their amplitudes add, and
`summarize_conversion_regret` reports the mean per grid point as `regret_osc_bar`. This is a
genuine within-run uncertainty, distinct from and invisible to a cross-solver comparison.

### Version 2026.7.15

#### Breaking (MCP): `base_plan_year1` replaces `deterministic_year1` in `run_year1_robustness`
The single-path comparator in the `run_year1_robustness` output is now reported under
`base_plan_year1` and carries a `rate_method` key identifying what that comparator is:
the case's configured rate method. The old name oversold determinism — the base solve
need not be deterministic (a seeded stochastic method yields one reproducible draw);
with a fixed-rate method such as `historical_average`, the base plan is the
conventional average-return plan, the natural single-number benchmark to contrast with
the scenario distribution.

#### Fixed
- The `filename=` path of the scenario MCP tools (`run_stochastic`,
  `run_year1_robustness`, `run_historical`, `run_monte_carlo`) silently dropped the
  case file's `[solver_options]` — bequest, maxRothConversion, previousMAGIs,
  startRothConversions, and the rest — and solved with defaults instead (a \$1 bequest,
  uncapped conversions), so results could differ materially from `run_case` on the
  same file. The case's options are now the base, rescaled from the file's \$k units to
  the MCP tools' full dollars, with explicit MCP arguments overriding
  (`_merge_case_opts`); regression tests pin the behavior. `run_case`,
  `explain_results`, and `compare_to_baseline` were already correct.

#### New: example case `dana`
`examples/Case_dana.toml` (+ `HFP_dana.xlsx`): a single Californian at the retirement
threshold — retired at the end of last year at 65, ≈\$1M of after-tax savings
concentrated in a \$937k traditional IRA, Social Security at 70, RMDs at 75, a \$400k
bequest target beside a home left to heirs. Designed for first-year
decision-robustness studies: plan year 1 is the first retirement year, so every
scenario shares one information set at the moment of the conversion decision;
conversions are deliberately uncapped and the base plan uses `historical_average`
rates.

### Version 2026.7.14

#### New: year-1 robustness — how confident should you be in this year's numbers? (`run_year1_robustness`)
Only the first year's decisions of a plan are executed; later years are re-optimized
as returns realize. The new `run_year1_robustness` MCP tool (the seventeenth, also
exposed on the Assistant page) solves the plan across historical or Monte Carlo
scenarios and reports the distribution of the first-year decisions: per-person Roth
conversion percentiles with the share of scenarios recommending a conversion and an
agreement metric (share within 10% of the median), withdrawals by account, net
spending, and the modal top tax bracket — next to the deterministic base-case
decisions for comparison. Answers "should I really convert \$X this year?" with
"convert \$45k–\$60k in 87% of scenarios" instead of a single-path number. The
underlying per-scenario decisions are available programmatically via the
`year1_decisions` key of `runStochasticSpending()` and the new `summarize_year1()`
helper exported from `owlplanner`.

#### New: explanations lead with this year and are grounded in every constraint
`explain_results` output now begins with a `this_year` section — the decisions to
execute now (per-person conversion, withdrawals, RMD due), the tax bracket being
filled and the headroom left in it, proximity to tax thresholds (NIIT, Medicare
IRMAA with its two-year lookback, ACA, Social Security taxability), and the marginal
value of a dollar today. Every constraint row in the optimization now carries a
machine-readable tag classified as user policy, accounting structure, or formulation
machinery, so binding-constraint reporting covers the full model and never leaks
internal big-M constructs. Policy-meaningful variable bounds are priced from reduced
costs as well: conversions disallowed by rule, the `minTaxableBalance` safety net,
and capital-gains bracket room. The payload is validated against a versioned schema
(`schema_version`) that documents every field. Explanations never require a MIP:
MILP tax modes are downgraded to the self-consistent loop for the explanation solve
(same shadow prices, a fraction of the cost), recorded in the caveats.

#### Fixed
- The reported value of relaxing a binding Roth-conversion cap had the wrong sign
  (it could show as negative; relaxing a cap can never hurt). Verified against
  finite differences.
- A seed set with `setReproducible()` after the rate model was constructed — the
  ordering used by the `seed` parameter of `run_stochastic` and
  `run_year1_robustness` — was silently ignored, making Monte Carlo runs
  non-reproducible. The scenario RNG now resets from the plan's authoritative seed.
- The Assistant chat page was missing the new `run_year1_robustness` tool; a test
  now pins the page's tool whitelist to the MCP registry so future tools cannot be
  silently skipped.

#### Documentation
The Mathematical Foundations paper (owl.pdf) now documents the state income tax
model and its LP formulation (the paper previously claimed state taxes were not
modeled), the `taxable_first` withdrawal-ordering gates, the constraint-tag taxonomy
behind the explanation engine, and the year-1 robustness measure with its
perfect-foresight caveat.

#### Maintenance
Dependencies refreshed to current releases (`make update`): streamlit 1.59.2,
plotly 6.9.0, uvicorn 0.51.0, websockets 16.1, cffi 2.1.0, and others; this also
moves off the yanked charset-normalizer 3.4.8. Full test suite passes on both
solvers against the upgraded environment.

### Version 2026.7.5

#### Breaking (MCP): `birth_years` replaced by `birth_dates` in the params tools
The params-driven MCP tools (`run_from_params`, `save_case`, `compare_to_baseline`,
`explain_results`, and the stochastic/backtest tools) now take full dates of birth
(`birth_dates=["1963-03-15", ...]`) instead of `birth_years`. The engine has always
been month-and-day precise — FRA, the monthly claiming-age factors, and the SSA
born-on-the-1st rule all use the full date — but the MCP layer previously collapsed
input to a July-1 assumption, introducing up to six months of error in Social
Security claiming math (material when `optimize_ss_ages` selects a claiming month)
and possible off-by-one calendar years for benefit, Medicare, and RMD starts. The
`owl_intake` interview now asks for dates of birth. `list_contribution_limits`
retains `birth_years` (IRS limits are year-based), and `convert_ss_benefit` already
accepted `birth_month`/`birth_day`.

#### New: MCP solve tools report their assumptions (`assumed_defaults`)
The params-driven MCP tools (`run_from_params`, `save_case`, `run_stochastic`,
`run_longevity_stochastic`, `run_historical`, `run_monte_carlo`) now report the material
assumptions made for omitted parameters in an `assumed_defaults` field of the response:
state (assumed TX — no state income tax), fixed `conservative` returns, taxable cost basis
(current-year appreciation only), missing Social Security benefits or claiming ages,
default 60/40→40/60 allocation glide, smile spending profile, couple survivor fraction,
heirs' tax rate, prior-year MAGIs (IRMAA lookback), and un-modeled pre-65 ACA coverage.
AI clients are instructed to relay these assumptions and ask for true values when they
matter. Accordingly, `state`, `spending_profile`, `survivor_fraction`, and the allocation
parameters now default to "unspecified" rather than silently assuming values.

#### New: embedded AI Assistant page (self-hosted/Docker, opt-in)
New chat page in the web UI that can read the case currently open in the app, run the
optimizer on variants, quantify strategies (`compare_to_baseline`), explain results
(`explain_results`), stress-test, and save scenarios as case files — reusing the same
tool implementations the MCP server exposes, in-process — including the case-file tools
(`list_cases`/`run_case`/`compare_cases`), which on a self-hosted install close the loop
with `save_case` (save a scenario, reload and re-run it in a later conversation). A
`get_current_case_results` session tool returns the solved year-by-year results the app
is displaying, so questions about an already-solved plan don't trigger a re-solve. The
page opens with a context-aware greeting and clickable starter prompts (explain my plan,
value of the strategy, probability of success, start a plan from scratch).
Strictly opt-in: the page is
registered only when `OWL_ASSISTANT=1` is set, so the hosted app never exposes it;
requires `pip install owlplanner[assistant]` (the `anthropic` package) and an
`ANTHROPIC_API_KEY` (`OWL_ASSISTANT_MODEL` overrides the default model;
`OWL_ASSISTANT_BASE_URL` / `OWL_ASSISTANT_API_KEY` point the assistant — without
affecting other Anthropic-SDK tools in the same shell — at any Anthropic-compatible
endpoint, e.g. a LiteLLM proxy in front of local models). Session access is read-only by
design — the chat serializes the open case through the tested `ui_to_config` path and
never mutates session state; scenarios are handed back via `save_case` files loadable
from the Create Case page. Conversations (including case data when asked about) are
sent to the configured AI provider, which the page discloses.

#### New: "Connect your AI" page in the web UI
New page under Tools that generates copy-paste MCP configuration for connecting Owl to
an AI assistant — Claude Desktop, Claude Code, Cursor, Gemini CLI, VS Code (Copilot or
Cline), Zed, and other MCP-compatible clients. Pick the client and install method
(uv checkout or `owlcli` on PATH), enter the repository path, and copy the generated
snippet, with per-client file locations and verification steps. The page is safe on the
hosted app: the MCP server itself always runs on the user's own computer, and the page
states the privacy boundary explicitly. Config-generation logic lives in
`ui/connectai.py` with unit tests plus an AppTest rendering test.

#### New: `explain_results` MCP tool — shadow-price explanations of a solved plan
New solver option `withDuals=True`: after the final solve, the LP is re-solved with the
binary variables fixed at their solution values (always via HiGHS) to extract constraint
duals and reduced costs. Key constraint rows are now tagged at construction
(`bequest_floor`, `cash_flow[n]`, `rmd[i,n]`, `profile_lo/hi[n]`), and a new
`explain_results` MCP tool turns the duals plus the primal solution into a structured
explanation: the lifetime-spending cost per dollar of bequest floor, the value of an
extra dollar of income in each year (the plan's endogenous discount curve), the cost of
each forced RMD dollar, the Roth conversion schedule with binding-cap values, per-year
federal bracket fill and headroom (from the `f_tn` bracket variables), and the account
depletion order. Sensitivities are marginal and hold bracket selections and
self-consistent quantities fixed at their converged values.

#### New: `compare_to_baseline` MCP tool — the value of optimization in dollars
New MCP tool that solves the same case twice — fully optimized, and restricted to a
conventional baseline strategy — and reports the advantage in today's dollars: extra
annual and lifetime spending, extra final bequest, and the tax/premium difference.
Baseline policies (all on by default): `no_roth_conversions`,
`no_ss_age_optimization` (claim at stated ages), and `taxable_first_ordering`
(withdraw taxable first, then tax-deferred beyond RMDs, then Roth). Accepts a TOML
case file or the same flat parameters as `run_from_params`. Both runs share one
rate-series seed so stochastic rate methods see identical market sequences (supported
by a new `reproducible_seed` pass-through in the parameter builder). The baseline is a
faithful conventional-wisdom strategy in which the optimizer only sizes withdrawals,
and it remains a restriction of the optimized problem — the reported advantage is a
certified lower bound (up to the solver gap).

#### New: `withdrawalOrder` solver option — enforce conventional withdrawal sequencing
New solver option `withdrawalOrder="taxable_first"` adds per-year household-level
gating binaries (`zo`) enforcing the conventional order: tax-deferred withdrawals
beyond the RMD are allowed only once the household taxable balance is exhausted, and
Roth withdrawals only once tax-deferred is also exhausted. RMDs remain forced, HSA
withdrawals are not gated, and surplus deposits land in taxable — closing the
drain-and-redeposit loophole. Default `"optimal"` leaves ordering free.

#### New: `owl_intake` MCP prompt and reference resources
The MCP server now exposes an `owl_intake` prompt — an interview script that tells the AI
client which questions must be asked before building a plan (state, balances, Social
Security, work status, pre-65 health coverage), which to ask only when applicable, and
which parameters may be assumed with disclosure — plus unit conventions (monthly vs
annual, wages net of contributions, corporate bonds vs Treasuries). The same text is
readable as the `owl://intake-checklist` resource, and `owl://modeling-capabilities`
serves the modeling-capabilities reference (now packaged in the wheel alongside
PARAMETERS.md).

#### Refactor: MCP tool implementations moved to `owlplanner.assistant.tools`
The fourteen MCP tool functions were extracted from `owlplanner/cli/cmd_serve.py` into a
new `owlplanner/assistant/tools.py` module that imports neither `mcp` nor `click`, so the
same tools can be reused by other assistant front ends. `cmd_serve.py` now only registers
the tools with FastMCP and provides the `owlcli serve` entry point. No behavior change.

---

### Version 2026.7.4

#### Bug
Fix broken imports incorrectly removed by linter that prevented the UI from functioning properly.

---

### Version 2026.7.3

#### New: save the Household Financial Profile back to a workbook
`Plan.saveHFP()` writes the HFP currently in effect to an Excel workbook that `readHFP()`
can read back, making the HFP a bidirectional serialization format (discussion #131).
Plans populated programmatically (values written from Python) have their time lists
reconstructed from the plan's arrays; plans loaded from an HFP preserve the original
401k/IRA column splits. On success, the plan's HFP filename is updated so a subsequent
`saveConfig()` references the saved workbook.

#### Behavior change: uniform wages convention — HSA contributions now netted out of wages
The *anticipated wages* column of the HFP is now defined as earned income net of **all**
contribution columns, with no exceptions. Previously, HSA contributions were the odd one
out: wages were entered gross of HSA and **Owl** deducted the contribution from taxable
income, provisional income, and MAGI itself — while the same dollars also remained counted
as spendable cash. The explicit deductions have been removed from the optimization model:
like every other contribution, HSA contributions are now excluded from both cash flow and
taxable income through the wages entry alone. This makes HSA treatment exact on both sides,
avoids over-deducting employer HSA contributions (which were never part of wages), and
brings the implementation in line with the equations of the accompanying paper, which never
included an explicit HSA deduction term.

**Migration**: if your HFP has nonzero *HSA ctrb* entries, lower *anticipated wages* in
those years by your own (payroll) HSA contributions. Cases with no HSA contributions are
unaffected. Expect slightly lower optimized spending/bequest for HSA cases (the former
deduction was a phantom benefit; all example cases shifted by roughly −0.3%).

The Wages and Contributions documentation was also tightened overall: it now states the
net-of-all-contributions convention precisely (employer portions in the *ctrb* columns are
never subtracted from wages), notes that contributions are not re-subtracted from the
annual cash-flow balance, and documents explicitly that after-tax (non-deductible)
contributions to tax-deferred accounts are not supported — no cost basis is tracked, so
every dollar withdrawn or converted is fully taxable.

---

### Version 2026.7.2

#### Maintenance
- Update dependencies due to vulnerabilities identified by GitHub's dependabot.

#### Documentation
- Improve documentation on how to build HFP file.

---

### Version 2026.6.18

#### References to images
Images are cached when local and are dispatched by a local service. This leads
to race conditions on Streamlit startup, leading to images not always being displayed.
Using URL for images pointing to GitHub brings two benefits:
- Bypass the caching service, avoiding the race condition
- Allow pypi.org to display images when re-using the README.md file per default.

But it has an inconvenience:
- **Owl** needs web access to be able to load images.

If a case surfaces where a user needs to run Owl in airgap mode we can revisit
this issue with a fallback approach.

#### Add UI doc to table in README.md

#### Licensing audit
Consistent copyright headers across all source files (GPLv3) and documentation (CC-BY-NC-SA-4.0, see `LICENSE-docs`).

---

### Version 2026.6.17

#### Fix: Cumulative Distribution Function (CDF) comparison year range
The last (latest) year is now included in CDF comparisons, which previously dropped it.

#### Example cases reviewed
Diversified the no-income-tax states across the example set, added a new deep-in-retirement
same-sex couple case (`helen+ruth`), and refreshed every case description to better reflect what
each scenario demonstrates.

#### Logo and images licensed separately from the GPL
The logo and image assets are now covered by their own `assets/LICENSE` rather than the GPL.

#### Maintenance
Updated dependencies to address a flagged vulnerability.

---

### Version 2026.6.16

### Owl has a new logo!
Consolidated images and made local references thus avoiding download from the internet.
The logo and favicon now live in a single repo-root `assets/` directory, and all UI references
were centralized to one source of truth (`LOGOFILE`/`FAVICONFILE` in `sskeys.py`), so the app no
longer fetches its branding from the internet at startup. Documentation (README, INSTALL, User
Guide, Docker) now points at the same `assets/` images.

---

### Version 2026.6.15

#### Balance Sheet graph

A new **Balance Sheet** graph on the **Graphs** page (Portfolio section) complements the
traditional and liquid balance-sheet worksheets. Assets (taxable, tax-deferred, tax-free, HSA,
fixed assets) are stacked above the zero line and liabilities (debt, deferred income tax on
tax-deferred/HSA balances, and fixed-asset disposition costs) below it, with the traditional and
liquid net-worth lines overlaid so the gap between gross and liquidatable wealth is visible at a
glance. Available as `Plan.showBalanceSheet()` for notebook use; honors the nominal/today's-dollars
toggle and renders in both the Plotly (UI) and Matplotlib (CLI/notebook) backends.

#### Fix: one-year net-worth dip when a fixed asset is sold

Corrected an accounting error in the beginning-of-year fixed-asset arrays. A disposed asset was
dropped from the balance sheet at the start of its disposition year, but its sale proceeds only
land in the savings accounts the following year, so net worth was under-counted for that one year
(an artificial dip in the Balance Sheet graph, worksheets, and per-year JSON). Fixed assets are
now counted through their disposition year and drop out the year after, when the proceeds appear,
keeping net worth continuous. The cash flow, taxes, and bequest values were already correct and
are unchanged.

#### Constrain-mean option for the VAR(1) rate model

The `constrain_mean` option (shift each generated series so its arithmetic mean matches the
historical calibration window, isolating sequence-of-return risk from sample fluctuation) is now
available for the `vector_ar` method, bringing it in line with the other historically-calibrated
stochastic models (`historical_gaussian`, `historical_lognormal`, `historical_copula`, `garch_dcc`,
`gmm`, `hmm`). The "Constrain mean" checkbox appears automatically on the **Rates** page when
`vector_ar` is selected.

#### Clearer "today's dollars" labeling on plots and in the UI

Inflation-adjusted plots now label the vertical axis as `$k (constant <year>)` (e.g.
`$k (constant 2026)`) instead of an ambiguous year tag, making the deflation base explicit and
pairing cleanly with the `$k (nominal)` antonym. This also fixes a rendering bug where the
dollar sign in the today's-dollars axis title was interpreted as a LaTeX/MathJax delimiter by
the Plotly static-image export, mangling the label. The matching tooltips on the **Graphs**
dollar-amount selector, the **Worksheets** "real (today's) dollars" toggle, and the **Goals**
bequest/spending/safety-net fields now spell out "constant `<year>` dollars", all keyed off a
new `baseYear()` helper so the wording always tracks the plan's base year.

#### Documentation

Added a Savings Balance example plot (the *chris+pat* case) to the README to illustrate how
Owl draws down tax-deferred accounts while growing tax-free Roth balances through optimized
early-retirement conversions.

#### Documentation reorganization

Hand-authored reference docs now live in a single top-level `info/` directory instead of being
split between the repository root and the Quarto site's output folder (`docs/`). `USER_GUIDE.md`,
`PARAMETERS.md`, `RATE_MODELS.md`, `mcp.md`, `modeling-capabilities.md`, and `year-end-update.md`
moved to `info/`; community-health files (`README`, `CHANGELOG`, `CONTRIBUTING`, `CREDITS`,
`LICENSE`, `INSTALL`) remain at the root. All internal links, the wheel `force-include` for
`PARAMETERS.md`, the CLI/UI path resolution, and the `make rate-model-docs` target were updated
accordingly, leaving `docs/` reserved for generated Quarto output.

Documentation images were likewise separated: the markdown screenshots and plots moved to
`info/images/`, leaving `papers/images/` for the LaTeX figures used by `owl.tex`; two unused
images were removed. Several long-broken references were fixed in passing — the `docs/images/`
image paths, the tutorial-notebook links, and the worked-example's data file
(`HFP_jack+jill.xlsx`) — and the `odfpy`/`uv` installation wording was clarified. A new
`make site` target renders the Quarto website and cleans up render artifacts (the demo workbook
and orphaned hashed assets).

### Version 2026.6.14

#### Balance sheets in worksheets (traditional and liquid)

Two new worksheets summarize total wealth by combining savings accounts, fixed assets, and
debts at the beginning of each year (plus a final end-of-plan bequest row). The **Balance
Sheet** uses traditional accounting at gross market value: assets (taxable, tax-deferred,
tax-free, HSA, fixed assets), `total assets`, `debt`, and `net worth`. The **Liquid Balance
Sheet** shows the same gross assets but adds future obligations as liabilities to estimate
realizable wealth: `debt`, `deferred income tax` (tax-deferred + HSA balances times a new
*Liquidation tax rate*), `disposition costs` (fixed-asset commission plus capital-gains tax
at a new *Liquidation cap-gains rate*, with the primary-residence exclusion applied),
`total liabilities`, and `liquid net worth`. Taxable savings are shown at face value and HSA
balances are treated as ordinary-taxable (a conservative estimate). Both rates are set on the
**Rates** page and saved with the case. The sheets appear under a new **Balance Sheets** tab
in the **Worksheets** page and honor all display options (nominal/today's dollars, optional
age columns, hide all-zero columns) and the Excel download.

#### MCP & CLI: balance sheet and net worth in results

The balance-sheet quantities are now reachable through the MCP server and CLI, not just the
Streamlit worksheets. `run_case`/`run_from_params` add the opening balance sheet to the
`summary` block (`net_worth_start_*`, `liquid_net_worth_start_*`, `fixed_assets_start_nominal`,
`debt_start_nominal`, `deferred_income_tax_start_nominal`) and the liquidation-rate
assumptions, plus per-year `fixed_assets`, `debt`, `net_worth`, `deferred_income_tax`,
`disposition_costs`, and `liquid_net_worth` in `by_year` (the existing `portfolio_total`
remains savings-only). `explain_case` now loads the HFP workbook so it can report the
`fixed_assets` and `debts` inputs and an `opening_balance_sheet` summary. `run_from_params`
and `save_case` accept new `liquidation_tax_rate` / `liquidation_capgains_rate` parameters
(percent), which `save_case` persists to the case TOML. A shared
`export.balance_sheet_arrays()` helper is the single source for the worksheet, the summary
metrics, and the JSON output so they stay consistent. Documented in `docs/mcp.md`.

#### Tests: generic schema-driven config round-trip guard

Added `tests/config/test_roundtrip_generic.py`, which introspects the Pydantic schema and
verifies every scalar parameter survives both the plan and UI config bridges, with a
completeness guard so a newly-added field that isn't wired (or consciously skip-listed) fails
loudly — replacing the need for a hand-written round-trip test per parameter.

---

### Version 2026.6.13

#### Fix: Social Security treatment in MAGI (IRMAA / NIIT vs ACA)

MAGI is now computed on two distinct bases instead of one. IRMAA (Medicare Part B/D
surcharges), the Net Investment Income Tax, and the OBBBA 65+ senior-deduction phaseout use
the **AGI-basis** MAGI (`MAGI_n`), which includes only the *taxable* portion of Social
Security — matching the statutory definition (SSA POMS HI 01101.010: AGI + tax-exempt
interest). The ACA premium credit (IRC §36B) and the Social Security provisional-income
formula continue to use the **full-SS** MAGI (`MAGI_aca_n`), which adds back the non-taxable
portion. Previously a single full-SS MAGI drove all of them, overstating IRMAA/NIIT/OBBBA
exposure for households collecting Social Security. The fix applies in both loop and
optimize modes (Medicare and NIIT MILP embeddings updated). `papers/owl.tex` updated to
match; reproducibility references shifted accordingly (bequest/spending rise slightly).

#### Robustness: Benders fall-back and LTCG bracket-partition bound

`withDecomposition="benders"` now falls back to the relax-and-fix heuristic when it cannot
certify optimality within the requested gap (keeping the better objective), instead of
silently returning an uncertified solution. The LTCG bracket-partition companion bound now
seeds its capital-loss buffer from the known fixed-asset capital gains so a first-iteration
fixed-asset loss cannot make the partition infeasible.

#### MCP: `list_contribution_limits` tool for IRS contribution ceilings

New MCP tool returns each person's maximum annual contribution to 401(k)/403(b)/457(b)/TSP,
IRA, and HSA accounts for a given tax year, including the age-50+ catch-up and the SECURE 2.0
"super" catch-up for ages 60-63. Helps AI assistants guide users in their 50s and 60s toward
maxing out tax-advantaged contributions before filling in the `contributions` list for
`run_from_params`/`save_case`. Adds `contributionLimits()` and a 2025/2026 limits table to
`tax_federal.py` (statutory ceilings only — does not check MAGI-based eligibility/phase-outs).

#### Per-cell Roth conversion overrides (discussion #129)

New `useRothConvOverrides` solver option lets the *Roth conv* column of the Wages and
Contributions table pin a year/individual's conversion to an exact amount — bypassing the
annual cap — or force it to zero, while every other year stays optimized. Replaces the
all-or-nothing `maxRothConversion="file"` mode.

**Breaking change:** `maxRothConversion="file"`
is no longer accepted (raises a validation error); update TOMLs to use `useRothConvOverrides`
instead. Run Options also gains a "Swap Roth converters mid-plan" control for couples,
mutually exclusive with the existing Roth-conversion exclusion selector.

#### CI: bump Node per GitHub's request
Bump `actions/checkout` and `astral-sh/setup-uv` to Node 24 releases ahead of GitHub's Node 20 deprecation.

---

### Version 2026.6.12

#### LTCG bracket-partition and state-tax LP fixes

Fixed an LP degeneracy that could let the 20%-LTCG-bracket variable (`q_pn[2,n]`) be
inflated far beyond the actual realized gain `Q_n` (most visible with
`maxRothConversion="file"`). A companion upper bound on the bracket-partition row in
`_configure_ltcg_constraints` now keeps `q_pn` tied to `Q_n`. The same flat-direction
pattern was also present for no-income-tax states (FL, TX, AK, ...): state-tax LP
variables (`st_f`/`st_e`/`st_re`) are now skipped entirely when every bracket rate is
zero, since they could never contribute to `st_T_n` anyway. Added a new regression test
for `maxRothConversion="file"`.

#### Balance-sheet arrays for fixed assets and debts (issue #128)

`Plan` exposes two new arrays (length N_n), computed in `processDebtsAndFixedAssets()`:
- `fixed_assets_current_asset_values_n` — gross market value of fixed assets still held
  at the start of each year (`fixedassets.get_fixed_assets_current_values_array`).
- `fixed_assets_debt_balances_remaining_n` — remaining loan balance at the start of each
  year (`debts.get_debt_balances_array`).

No commission or tax treatment applied — simple snapshots for a future balance-sheet worksheet.

---

### Version 2026.6.9

#### MCP server — AI assistant access to Owl

Owl is now accessible as a tool to AI assistants that support the
[Model Context Protocol](https://modelcontextprotocol.io) (MCP): Claude Desktop, Claude Code,
Cursor, Zed, VS Code (GitHub Copilot 1.99+ or Cline extension), Windsurf, and any other
MCP-compatible client.

**New MCP tools:**

- **`run_from_params`**: Build and solve a retirement plan directly from structured parameters
  (names, birth years, account balances, SS benefits, etc.) without preparing any files. AI
  assistants can describe a financial situation in natural language and immediately get an
  optimized plan back as JSON.
- **`save_case`**: Persist a flat-parameter plan to disk as a TOML case file and an HFP
  workbook (`.xlsx`). Useful for saving AI-generated plans for later UI use.
- **`run_stochastic`**: Compute the stochastic spending efficient frontier from either a TOML
  file or flat parameters. Accepts `"historical"` (back-test) or `"mc"` (Monte Carlo) scenarios,
  sweeps risk-aversion parameter λ across the frontier, and returns committed spending at a
  target success rate and the full efficient frontier — all as structured JSON.
- **`convert_ss_benefit`**: Utility tool that converts between a Social Security PIA
  (Primary Insurance Amount, the benefit at Full Retirement Age) and the actual monthly
  benefit at a given claiming age, in either direction. Lets an AI assistant turn a
  statement like "I'm 65 and I get a \$2,800 check" into the PIA value expected by
  `ss_monthly_pias` in `run_from_params`, `save_case`, `run_stochastic`,
  `run_longevity_stochastic`, `run_historical`, and `run_monte_carlo`.

**MCP parameter coverage — all three tools (`run_from_params`, `save_case`, `run_stochastic`):**

All monetary values use full dollars (`$`) throughout the MCP interface via `units="1"`.

- **Unit convention**: All account balances, solver limits, and monetary options use full
  dollars (`$`). Social Security is the monthly PIA in `$/month` (matching the Plan API's
  `setSocialSecurity()`). Pensions are monthly `$/month`. Time-series amounts (wages,
  contributions) are `$/year`.
- **`ss_monthly_pias`**: Monthly Social Security PIA per person — the benefit at Full
  Retirement Age from the SSA statement (e.g. `[2667, 1833]`). Renamed from the initial
  annual-amount convention.
- **`min_taxable_balance`**: Per-person inflation-indexed floor on the taxable account
  balance (emergency fund / safety net). The optimizer will not draw the taxable account
  below this amount in any year.
- **`spending_profile`**: Retirement spending shape — `"smile"` (default, go-go/slow-go/
  no-go curve) or `"flat"` (constant inflation-adjusted spending). Companions:
  - `smile_dip` — depth of the slow-go spending dip in % (default 15).
  - `smile_increase` — additional spending growth toward no-go years for medical costs in %
    (default 12). Can be negative to model a declining-spending trajectory.
  - `smile_delay` — number of initial go-go years held flat before the smile curve begins
    (default 0).
- **`spias`**: List of Single Premium Immediate Annuities. Each entry specifies
  `person`, `buy_year`, `premium` (deducted automatically from the IRA as a non-taxable
  rollover), `monthly_income`, `indexed` (CPI-linked), and `survivor_fraction`.
  Supports multiple SPIAs per plan and pre-purchased annuities (`buy_year` before plan start).
- **`start_roth_year`**: 4-digit year before which no Roth conversions are allowed. Useful
  when the user expects to remain in a high tax bracket for several years.
- **`no_roth_person`**: Name of the individual excluded from all Roth conversions (couples only).
- **`max_roth_conversion`**: Annual per-person Roth conversion cap in `$/year`.
- **`bequest`**: Target estate value in today's dollars when `objective="maxSpending"`.
  The optimizer maximizes spending subject to leaving at least this amount to heirs.
- **`optimize_ss_ages`**: Boolean — if `True`, the MIP optimizes the Social Security
  claiming month for each person (ages 62–70, monthly resolution) instead of using the
  fixed `ss_ages` values.

**Documentation (`docs/mcp.md`):**

- Full setup instructions for Claude Desktop, Claude Code (CLI), Cursor, Zed, VS Code
  (GitHub Copilot + `.vscode/mcp.json` format; Cline extension format), and Windsurf.
- `run_stochastic` added to the tools reference table and example interaction section.
- All example interactions updated to use monthly PIA language (was annual benefit).
- New example: Robert with `min_taxable_balance` (emergency fund / safety net).
- New example: SPIA comparison — AI fetches current payout rates from the web and
  compares the plan with and without converting a portion of the IRA to a SPIA.

**README and Streamlit Welcome page:**

- MCP listed as the fourth way to run Owl alongside cloud, Docker, and native install.
- AI assistant bullet added to the key capabilities list, naming all supported clients.
- SEO-friendly H3 heading (*AI-powered retirement planning — ask your AI assistant*) added
  to the Welcome page.

**Modeling capabilities (`docs/modeling-capabilities.md`):**

- New *Access interfaces* table below the modeling table listing all four access modes
  (Streamlit UI, Python API, CLI, AI assistant/MCP).

**Tests:**

- `tests/test_mcp_params.py` (53 tests): `_build_plan_from_params`, `_build_hfp_dataframes`,
  `save_case` round-trip, `run_from_params` integration tests, and 5 new SPIA unit tests.
- `tests/test_mcp_stochastic.py` (30 tests): `_stochastic_blocking`, `_build_stochastic_json`,
  and `run_stochastic` async end-to-end tests covering historical and MC paths, error handling,
  and frontier monotonicity.

---

### Version 2026.6.7

#### Python

Pinned version to 3.14 for Streamlit Cloud Server and uv deployment.
However, versions >= 3.11 are fine for owlplanner package.
Docker containers are using an image with Python 3.14.

#### State income tax

State income tax brackets are now embedded directly in the LP alongside federal taxes,
giving the optimizer full visibility into state marginal rates when planning Roth conversions,
withdrawals, and spending.

A new `state` field in `[basic_info]` accepts any two-letter US state abbreviation (e.g.
`state = "MN"`). Leaving it blank or omitting it preserves the previous federal-only behavior.
No-income-tax states (AK, FL, NV, NH, SD, TN, TX, WA, WY) are accepted and simply contribute
zero state tax.

State tax is modeled using the same graduated-bracket mechanism as federal income tax:
- **Brackets and marginal rates** — state-specific, inflation-adjusted each year.
- **State standard deduction** — subtracted from state taxable income, inflation-adjusted.
- **Retirement income exemption** — optional age-gated per-person dollar cap (e.g. GA, NY, PA).
- **Pension-only exemption** — separate cap where states distinguish pension from other retirement income.
- **Social Security treatment** — binary flag; states that tax SS (e.g. MN, VT) include
  85% of SS benefits in state taxable income.

Filing status transitions from MFJ to Single at the year the first spouse dies, matching
the federal filing-status transition already in the optimizer.

**New public method:** `Plan.setStateTax(state)`.
**New module:** `src/owlplanner/tax_state.py` — `st_taxParams()`, `valid_states()`.
**New data file:** `src/owlplanner/data/taxes_state.toml` — all 50 states + DC with 2026 rates.
**UI:** State selectbox added to the **Create Case** page.
**Output:** State tax appears as a separate series in `showTaxes()`, as a standalone line in
the plan summary (*Total state income tax paid*), and as a *State tx* column in the
income tax worksheet.

**Worksheet renamed:** The *Federal Income Tax* worksheet in the plan workbook is now called
*Taxes*, reflecting that it includes both federal and state tax detail.

**Cash flow fix:** State income tax was missing from the *Cash Flow* worksheet and CSV export,
causing the sheet to not balance when a state is configured. Fixed; test coverage added.

**Taxes worksheet:** Now includes Medicare+IRMAA and ACA premiums (when applicable) for a
complete year-by-year view of all optimizer-managed costs.

#### 2026 state tax data audit

All 51 jurisdictions in `taxes_state.toml` were verified against official 2026 sources, with
bracket and rate corrections applied to 21 states.

#### `tax2026.py` renamed to `tax_federal.py`

The federal tax module `tax2026.py` was renamed to `tax_federal.py` for consistency with
the new `tax_state.py` module. All internal imports updated; no public API change.

#### Drop Python 3.10 support

Python 3.10 is no longer supported. The minimum required version is now **Python 3.11**.
CI tests against Python 3.11, 3.12, 3.13, and 3.14.

#### MOSEK moved to required dependencies

MOSEK was previously an optional extra (`pip install owlplanner[mosek]`). It is now listed
as a standard dependency. Users without a MOSEK license can still install and run Owl — the
HiGHS solver remains the default and no license is required for normal use.

#### In-app documentation audit

The in-app help (**Documentation** page) was audited page-by-page against the actual UI and
brought back into alignment, including the state-tax help, **Worksheets** tab names, Monte-Carlo
rate-method lists, and a new experimental note on the Retirement Efficiency Score (RES). A couple
of stale UI labels were corrected along the way.

#### Versioning and committed lockfile

The package version is now a static field in `pyproject.toml` (single source of truth),
mirrored into `src/owlplanner/version.py` via `make sync-version` and guarded by a test.
uv now records this version natively in `uv.lock`, which is committed to the repository
(previously excluded because Streamlit Cloud could not parse the versionless editable entry).
Version numbers now use canonical PEP 440 form with no zero-padding (`YYYY.M.D`, e.g. `2026.6.7`),
so the string is identical across `pyproject.toml`, the wheel metadata, and `uv.lock`.

---

### Version 2026.06.06

#### Rate CDF plot (`showRatesCDF`)

Adds a new plot showing the empirical cumulative distribution function (CDF) of each asset class's generated
rates (S&P 500, Bonds Baa, T-Notes, Inflation), one panel per asset class.
For historical methods, the empirical CDF of the selected frm–to window is overlaid as a dashed gray line for goodness-of-fit comparison.
The y-axis gives cumulative probability directly — no binning artifact — making tail probabilities easy to read.
Constant-rate methods do not produce a CDF plot.

The same 2 000-sample representative draw used for the correlation graph is used here, so the CDF reflects the model's true distribution rather than the short plan-horizon realization.

**New public method:** `Plan.showRatesCDF(tag="", figure=False)`.
**New backend methods:** `plot_rates_cdf` in both `matplotlib_backend.py` and `plotly_backend.py`, declared abstract in `plotting/base.py`.
**UI:** Appears on the **Rates** page (left column, below *Selected Rates Over Time Horizon*) and on the **Graphs** page under the **Rates** tab, for varying rate methods only.

---

#### Constrain mean option for history-fitted stochastic rate models

Adds an optional `constrain_mean` parameter (default `False`) to six history-fitted stochastic rate models: `historical_gaussian`, `historical_lognormal`, `historical_copula`, `garch_dcc`, `gmm`, and `hmm`.

When enabled, each generated rate series is post-processed with an additive per-column shift so its arithmetic mean exactly matches the historical arithmetic mean of the selected window.
The distribution shape — variance, skew, volatility clustering, and cross-asset correlations — is fully preserved; only the mean is corrected.
This isolates sequence-of-returns risk from mean-estimation noise, which is useful when comparing scenarios across methods or plan horizons.

A **Constrain mean** checkbox is exposed in the Rates UI next to the year-range selectors for the six supported methods.
Return floors are applied after the mean correction: equity, bonds, and T-notes are floored at −100%; inflation is floored at −5%.

**New helper functions** in `src/owlplanner/rate_models/_builtin_impl.py`: `constrain_series_mean` (pure additive shift, no flooring), `_historical_arith_means` (arithmetic mean of the selected window from in-memory globals), and `apply_return_floors` (universal floor applied as the final step of every `generate()` method).

**`CONSTRAIN_MEAN_METHODS`** constant added to `constants.py`; sync between this constant and each model's `optional_parameters` is enforced by a new test (`tests/test_rate_models.py::test_constrain_mean_methods_in_sync`).

---

### Version 2026.06.05

#### New rate model — Gaussian Copula (`historical_copula`)

Adds a non-parametric Gaussian copula rate model fitted to the selected historical window.
Each asset's marginal distribution is preserved exactly via a rank-based empirical CDF — no Gaussian or log-normal shape is imposed on any marginal — while joint dependence is captured by a 4×4 copula correlation matrix in normal space.
New year-combinations are generated that were not observed historically but honour all pairwise rank correlations.
Generated values are bounded to the historical `[min, max]` of each asset class; inflation is floored at −5% to exclude Great Depression tail artefacts.
The empirical quantile resolution equals the number of years T in the selected window.

Registered in `STOCHASTIC_METHODS`, `HISTORICAL_STOCHASTIC_METHODS`, `VARYING_TYPE_UI`, and `HISTORICAL_RANGE_METHODS` in `constants.py`.
Exposed in the Rates UI alongside the other varying-rate methods; seed and reproducibility controls apply.
`HISTORICAL_STOCHASTIC_METHODS` is a new constant replacing the repeated inline method tuples in `owlbridge.py`, `plotly_backend.py`, and `matplotlib_backend.py`.

**New file:** `src/owlplanner/rate_models/copula.py` — `generate_histocopula_series`, `HistoCopulaRateModel`.

**Documentation:** `PARAMETERS.md`, `docs/modeling-capabilities.md`, `ui/Documentation.py` (method description, comparison table, correlation graph table, Monte Carlo section, reproducible rates, references — Sklar 1959).

---

#### Documentation and schema alignment (issue #126)

Added `fixedSpending` and `hsa` as explicit fields in the Pydantic schema (`SolverOptions` and `AssetAllocation`). Removed stale `spendingFloor`, `spendingWeight`, and `maxHybrid` references from `PARAMETERS.md`.

---

#### Inflation skewness correction for parametric rate models

Historical US inflation rates are right-skewed (long right tail from high-inflation episodes such as the 1970s), which violates the Gaussian residual assumption implicit in four parametric stochastic models.
A piecewise-linear (PWL) normalization transform $\varphi$ is now automatically applied to the inflation dimension before fitting those models, and its inverse $\varphi^{-1}$ is applied to generated samples so outputs remain in actual inflation units:

$$\varphi(z) = \begin{cases} (z-\kappa)\,s^- + \kappa & z \le \kappa \\ (z-\kappa)\,s^+ + \kappa & z > \kappa \end{cases}$$

where $\kappa$ is the empirical median of the selected historical window.
The slopes $s^-$ and $s^+$ are auto-fitted by minimizing squared skewness of $\varphi(z)$ with a small regularization toward the identity, so they adapt automatically when the user changes the date range.
For US inflation over 1928–2025 the optimizer typically finds $s^- \approx 2.3$, $s^+ \approx 0.8$.
Fitted values are reported in the debug log at model initialization.

**Affected models:**
- `historical_gaussian`, `vector_ar`, `garch_dcc` — transform applied in return space.
- `historical_lognormal` — transform applied in log-return space to avoid log-domain constraints.

**Unaffected:** `gaussian`, `lognormal` (user-supplied parameters), `historical_bootstrap`, `historical_average`, `gmm`, `hmm` (no Gaussian residual assumption on inflation).

**New module:** `src/owlplanner/rate_models/inflation_transform.py` — `fit_inflation_transform`, `pwl_transform`, `inv_pwl_transform`.

**Documentation:** `papers/owl.tex` §"Inflation skewness correction", `docs/modeling-capabilities.md`, `ui/Documentation.py`.

---

### Version 2026.06.05

#### New rate model — Hidden Markov Model (`hmm`)

Adds a Hidden Markov Model rate model that extends the GMM by fitting a $K \times K$ Markov transition matrix between regimes via the Baum-Welch algorithm. Consecutive simulated years are no longer independent: regime persistence produces realistic multi-year bull and bear runs, capturing sequence-of-returns risk that the i.i.d. GMM cannot reproduce. Exposed in the UI with a configurable number of regimes (default $K=3$). The correlation plot uses 2 000 synthetic draws from the fitted model. Registered in `STOCHASTIC_METHODS`, `VARYING_TYPE_UI`, and `HISTORICAL_RANGE_METHODS`; seed and reproducibility controls work identically to `gmm`.

---

### Version 2026.06.04

#### New rate model — Gaussian Mixture Model (`gmm`)

Adds a multivariate GMM rate model that fits $K$ Gaussian components on the selected historical window via EM, capturing regime-dependent cross-asset correlations (bull, bear, crisis). Exposed in the UI alongside the other varying-rate methods, with a configurable number of components (default $K=3$).

---

### Version 2026.06.03

#### Bug fix — NIIT MILP (`withNIIT="optimize"`)

The MAGI equality constraint in `_add_magi_lp` incorrectly expressed $Q_n$
(LTCG capital gains) as `q_total − portfolio_LP_expression`.
At the LTCG partition minimum where `q_total = Q_n`, these two expressions
cancel, silently removing $Q_n$ from MAGI.
As a result, the optimizer computed NIIT as $0.038 \times \mathbb{I}_n$
instead of the correct $0.038 \times \min(\text{MAGI} - T,\; \mathbb{I}_n + Q_n)$,
understating NIIT by up to $0.038 \times Q_n$ per year when the NII cap was binding.

**Fix:** The MAGI LP constraint now uses the LTCG bracket allocation variables
$q^{(0)}_n + q^{(1)}_n + q^{(2)}_n$ directly for $Q_n$ (which equals the true
capital gains at the partition minimum).
The portfolio b/w/d LP expression is no longer subtracted.

**Regression test added:** `test_niit_optimize_large_taxable_J_n_vs_reference`
uses a large taxable balance to exercise the NII-cap path with significant $Q_n$.

#### Cash Flow worksheet — NIIT column

`ord taxes` in the Cash Flow worksheet now reports income tax ($T_n$) only.
NIIT ($J_n$) is shown as a separate `NIIT` column, consistent with how
`div taxes` ($U_n$) is already separated from income tax.
The `NIIT` column also appears in the CSV export.

---

### Version 2026.06.01

#### UI improvements

- **Documentation and Parameters Reference** — all expanders now use `type="compact"`
  with bold orange titles, giving each section a clear visual boundary consistent
  with the rest of the app styling.
- **Reports page** — download buttons are grouped into labeled *Input files* and
  *Output files* sections for clearer navigation.

#### Bug fix

- **Reports comparison** — `build_summary_dic()` now always emits `Total debt payments`
  and `Total ACA premiums paid` fields (with \$0 when none apply), so `compareSummaries()`
  no longer silently drops cases whose column sets differ when one case has debts or ACA
  costs and another does not.

#### Refactor

- **Logging** — all config modules (`toml_io.py`, `ui_bridge.py`) now route warnings
  through `mylogging` instead of the stdlib `logging` module, so messages appear
  consistently in the Streamlit case log.

---

### Version 2026.05.27

#### Rate method names — consistency and accessibility

All rate method names now use underscore separators and plain-language labels.
Old names are accepted as backward-compatible aliases (with a deprecation warning
logged on load) and will be removed in a future release.

| Old name | New name |
|---|---|
| `historical average` | `historical_average` |
| `trailing-30` | `trailing_30` |
| `histogaussian` | `historical_gaussian` |
| `histolognormal` | `historical_lognormal` |
| `bootstrap_sor` | `historical_bootstrap` |
| `var` | `vector_ar` |

Source files renamed accordingly:
`bootstrap_sor.py/.md` → `historical_bootstrap.py/.md`,
`var_model.py` → `vector_ar.py`.

#### Bootstrap documentation

- Tooltip and UI documentation clarify that `block_size` is a **fixed** block
  length for `block`/`circular`, but the **expected** (geometric mean) block length
  for `stationary`.
- All three non-iid variants collapse to iid when `block_size = 1`.
- Recommended range for annual return data: **3–5** (Politis & White 2004).

#### Bug fix

- `OWL_TEST_SOLVER` environment variable comparison is now case-insensitive
  (`highs`, `HiGHS`, and `HIGHS` all select the HiGHS solver in tests).

---

### Version 2026.05.24

#### Fixed assets — real vs. nominal growth rate

The `rate` column in the *Fixed Assets* HFP sheet now has **type-dependent semantics**:

- **Physical assets** (*residence*, *real estate*, *collectibles*, *precious metals*): `rate` is a
  **real (inflation-adjusted)** annual growth rate. Setting `rate = 0` means the asset maintains its
  purchasing power by tracking inflation. A value of `1` means 1 % above inflation per year.
  Shiller's long-run US data shows roughly 0–0.5 % real appreciation for real estate, so `0` is a
  reasonable default.
- **Financial assets** (*stocks*, *fixed annuity*): `rate` remains a **nominal** annual growth rate,
  unchanged from prior behavior.

**Migration:** existing HFP files that had a nominal rate (e.g. `3`) for a residence or real estate
asset should be updated. A rate of `0` now correctly means "tracks inflation" rather than "flat
nominal." All bundled example HFP files have been updated (residence and real estate rates set to `0`).

---

### Version 2026.05.23

#### Graphs

- **Annual cash flow mix** — new `showCashFlowMix()` chart: normalized stacked-area panels showing
  income sources (left) and outflow composition (right) as a percentage per year in today's dollars.
  Colors match the lifetime allocation pie charts. Wired into the Spending graphs section.
- **Lifetime allocation layout** — pie chart order swapped: income sources left, outflows right
  (both backends).

#### Bug fix

- **TOML parse errors now raise `ValueError`** instead of the misleading `FileNotFoundError`
  when a case file contains invalid TOML (e.g. a mixed int/float array like `[10.0, 2_000]`).
- **`Case_jack+jill` example** — corrected Jill's pension from `10.5` to `2_000.0` \$/month
  (issue #125); expected spending basis updated in regression tests.

---

### Version 2026.05.20

#### Mortality tables — SOA Pub-2010 public-sector tables

- Added **Pub2010-Safety**, **Pub2010-General**, and **Pub2010-Teacher** tables from mort.soa.org.
- Dropdown and documentation now ordered by life expectancy at 65 (shortest to longest).

#### Spending Optimization — longevity plots

- **Survival curves** — when longevity risk is enabled, a new chart shows P(alive at age X)
  for each individual derived from the selected mortality table. For couples, a dashed joint
  (last-survivor) curve is also plotted.
- **Drawn lifespans histogram** — overlapping histograms of the ages at death sampled across
  all Monte Carlo scenarios, one series per individual and one for the joint last-survivor
  horizon. Median age at death for each series is shown in a color-coded text box.
- **matplotlib stubs** — `plot_stochastic_cvar_vs_pos` and `plot_stochastic_res_vs_cvar`
  added as stubs returning `None` in the matplotlib backend (RES section is plotly-only for now).
- **Documentation** updated in the *Spending Optimization* section to describe the new charts.

---

### Version 2026.05.19

#### UX
- **Financial Profile page**: A status caption now appears below the HFP upload widget confirming
  which file was loaded. If any table value is edited after the upload, the filename is marked with
  a trailing `*` (e.g. `HFP_jack+jill.xlsx *`) so the original filename is never lost and the
  modified state is immediately visible without having to run the plan first.

---

### Version 2026.05.16

#### Taxable account cost-basis tracking

- **`setCostBasis(amounts, units='k')`** (new): Declares the aggregate cost basis of each
  individual's taxable account. When provided, capital-gains tax on taxable-account withdrawals
  is computed using the **average-cost method**: the gain fraction `(balance − basis) / balance`
  is applied per dollar withdrawn, capturing all embedded unrealized gains rather than only
  this year's price appreciation. The basis evolves each SC-loop iteration as withdrawals reduce
  it proportionally and new contributions (HFP deposits and LP surplus deposits) increase it at
  full cost.
- **Fallback**: If `setCostBasis` is not called, the prior approximation (`cap_rate ≈ τ₀ − μ`,
  this year's appreciation only) is used — no behavioral change for existing cases.
- **TOML**: `taxable_cost_basis` field in `[savings_assets]`; round-tripped through
  `saveConfig()` / `readConfig()`.
- **UI**: Per-person cost-basis inputs on the *Account Balances* page (optional; leave at 0 to
  use the legacy approximation).
- **Example files**: `Case_jack+jill`, `Case_joe`, and `Case_robin` updated with realistic
  cost-basis values (roughly half of taxable balance, consistent with ~10 years of compounding).
- **Docs**: `docs/modeling-capabilities.md` corrected — taxable-account gain treatment now
  accurately described as average-cost rather than LIFO.
- **Tests**: 8 new tests in `tests/test_cost_basis.py` covering backward compatibility,
  high-gain scenarios, edge cases (zero basis, full basis, basis > balance), and SC-loop
  convergence.

---

### Version 2026.05.15

#### UX
- Rework _Graphs_, _Worksheets_,  and _Create Case_ pages.
- Updated documentation.

---

### Version 2026.05.11

#### Hardening
- **Tests**: Add cash flow balance test
- **Advisory**: Upgrade requirements per GitHub advisory
- **Clean up**: Make HFP I/O consistent with new names for files

---

### Version 2026.05.07

#### Theme

- **Streamlit theme**: Remove default dark theme and leave it to system's settings.

#### Plots
- Improve threshhold for displaying QME values.

#### Cleanup
- Remove legacy names in HFP I/O.

---

### Version 2026.05.06

#### HSA qualified medical expense cap

- **`setMedicalExpenses(amount)`**: new method to declare annual non-Medicare qualified medical
  expenses (dental, vision, co-pays, deductibles). HSA withdrawals are now capped at
  Medicare costs + this amount per year, enforced as an LP constraint. Pre-Medicare years:
  only `setMedicalExpenses` amount is eligible (Medicare costs are zero). Without this call,
  HSA is limited to Medicare costs only; pre-Medicare HSA withdrawals default to zero — the
  tax-law-correct conservative default. Available in TOML via `optimization_parameters.other_medical_expenses`
  and in the UI under **Run Options → Health Insurance → Other Qualified Medical Expenses**,
  alongside Medicare and ACA settings.

#### HSA depletion graph

- **Stacked withdrawals**: `showHSA()` now splits the withdrawal area into a Medicare portion
  (attributed to Medicare costs, distinct color) and a `QME` portion (remaining qualified
  medical withdrawals),
  using stacked filled areas. Zero-valued series are suppressed from the legend.

#### HSA reporting

- **Cash Flow cleanup**: Removed `HSA→Medicare` from the **Cash Flow** worksheet so rows keep
  the balancing identity.
- **New HSA worksheet**: Added a dedicated **HSA** worksheet with `Medicare`, `QME`,
  `HSA total wdrwl`, `HSA→Medicare`, and `HSA→QME`, plus per-individual HSA balances,
  contributions, and withdrawals.

--- 

### Version 2026.05.06

#### Summary sheet refactor

- **Structured sections**: the Summary worksheet now groups entries under labelled section dividers
  (*Overview*, *Spending & income*, *Taxes & premiums*, *Partial bequest*, *Final bequest*,
  *Plan & solver*) for easier reading and navigation.
- **Currency formatting**: a `_parse_usd_string` helper centralises conversion of `u.d()` output
  to float so that numeric cells are stored as numbers rather than strings, enabling Excel
  formulas and sorting.
- **Reports UI**: the Reports page and its session-state keys updated in lock-step with the new
  export structure.
- **Tests**: `tests/test_export.py` and `tests/test_summary.py` each extended with 15 additional
  assertions covering section headers and numeric cell types.

#### Solver option round-trip fix

- **`SOLVER_UI_PASSTHROUGH_KEYS`**: a single authoritative list in `config/ui_bridge.py` of all
  solver options that are copied verbatim between the TOML/Plan solver options and the flat UI
  case dict. Options with dedicated UI translations (`withMedicare`, `withACA`, `withDecomposition`,
  `previousMAGIs`, etc.) are handled separately and excluded from the list.
- **Lifecycle fix**: solver options were not reliably preserved across UI navigation; the new
  passthrough mechanism ensures a lossless round-trip for all 30+ passthrough keys.
- **Tests**: 111 new assertions in `tests/test_config_ui_bridge.py` covering round-trip
  correctness for every passthrough key.

#### Bug fixes

- **Empty spending profile navigation**: fixed a UI crash when navigating to the Financial Profile
  page with an uninitialised profile.
- **Goals page alignment**: minor layout fix after the `maxHybrid` removal left a misaligned
  control row.

#### Savings Retention Margin chart

- **`showRetentionMargin()`** replaces `showSavingsRetentionRate()`: the new chart plots the annual
  difference between the savings retention rate and the real break-even threshold (in percentage
  points), so the zero axis is the neutral boundary. Blue bars indicate years where real wealth
  is growing; red bars indicate years where it is shrinking. The break-even line is no longer
  overlaid — it *is* the axis.
- **Log scale removed**: the log-scale toggle added no actionable information to the diverging
  chart and has been removed from the UI.
- **`plot_retention_margin`** added to both the Plotly and Matplotlib backends; the old
  `plot_savings_retention_rate` function has been removed from all backends and the base class.

---

### Version 2026.05.04

#### Remove maxHybrid objective

- **`maxHybrid` removed**: The hybrid objective (blending spending and bequest via a weight
  parameter `h`) has been removed. Because the LP objective is linear, it always drives
  spending to an extreme (floor or cap), providing no useful intermediate behavior that
  `maxSpending` with a bequest constraint or `maxBequest` with a spending constraint cannot
  achieve more directly.
- **Spending profile now always bilateral**: The profile slack (±slack%) is enforced as a
  symmetric bilateral bound for both `maxSpending` and `maxBequest`. The former one-way
  (floor-only) treatment that existed for `maxHybrid` is gone with the objective.
- **Options removed**: `spendingWeight` and `spendingFloor` solver options are no longer
  accepted (passing them logs an "unknown option" warning as with any unrecognized key).
- **`fixedSpending` and `spendingSlack` unchanged**: Both still work as before.
- **UI**: Goals page now offers two objectives (*Net spending* and *Bequest*) with no weight
  or floor controls; profile slack help text updated accordingly.
- **Schema**: `spendingWeight` and `spendingFloor` fields removed from the config schema.
- **Tests**: `tests/test_hybrid_objective.py` removed (214 lines, no replacement needed).

---

### Version 2026.05.03

#### ACA improvements for couples

- **Automatic SLCSP scaling**: When one spouse transitions from an ACA marketplace plan to
  Medicare, the benchmark Silver plan premium (`slcsp_annual`) is automatically scaled down
  to the remaining spouse's individual plan using the CMS age rating curve (45 CFR 147.102).
  The scaling factor is `f_younger / (f_older + f_younger)`, evaluated at the transition year,
  and ranges from roughly 37–48% of the combined household premium depending on the age gap.
  Users should set `slcsp_annual` to the **combined household premium**; no manual adjustment
  is needed for the transition years.
- **Age rating table**: CMS age rating factors (ages 0–64) are now stored in
  `src/owlplanner/data/aca_age_rating.py` alongside other regulatory tables.
- **`start_year` validation**: `setACA(start_year=N)` now raises a `ValueError` with a clear
  message if `N` is between 1 and 1999, catching the common mistake of entering an offset
  (e.g. `3`) instead of a 4-digit calendar year (e.g. `2029`). The UI field label and help
  text have been updated accordingly.
- **Tests**: 7 new tests (`TestACACoupleSLCSPScaling` and offset guard tests); total 35 in
  `tests/test_aca.py`.

---

### Version 2026.05.01

#### SPIA (Single Premium Immediate Annuity)

- **`addSPIA(individual, buy_year, premium, monthly_income, indexed, survivor_fraction)`**:
  Adds a qualified SPIA funded by a tax-deferred IRA rollover. Premium is deducted from the
  tax-deferred account in the buy year (non-taxable transfer); income begins in the same year
  and is fully taxable as ordinary income. Optional CPI indexing and joint-and-survivor fraction
  for couples. Multiple SPIAs per plan supported. Pre-purchased annuities (`buy_year` before plan
  start) generate income from year 0 with no premium deduction.
- **UI**: New *SPIA* section on the Fixed Income page with data editor for annuitant, buy year,
  premium, monthly income, CPI-linked flag, and survivor fraction (couples only).
- **Schema**: `spia_individuals`, `spia_buy_years`, `spia_premiums`, `spia_monthly_incomes`,
  `spia_indexed`, `spia_survivor_fractions` fields added to `[fixed_income]`.
- **Docs**: `PARAMETERS.md` SPIA section; `modeling-capabilities.md` SPIA row.
- **Tests**: 11 tests in `tests/test_spia.py` including TOML round-trip and clone round-trip.

#### Retirement Efficiency Score (RES) — experimental

- **`compute_res` / `compute_cvar`** (new, public API): Compute the floor-capped CVaR and the
  Retirement Efficiency Score (RES = committed spending above floor / CVaR) across the efficient
  frontier. `rho_star` is the success rate that maximizes RES. Exported from `owlplanner`.
- RES is shown as an experimental expander in the Spending Optimization UI for **historical
  scenarios only**. MC RES is suppressed — the lognormal tail structure produces unreliable ρ\*.
- **Docs**: `modeling-capabilities.md` RES row.

#### SC loop convergence refactor

- Convergence logic extracted into helper methods (`_check_obj_convergence`, `_check_cycle`,
  `_check_stagnation`, `_check_max_iterations`) and `_build_sc_loop_policy()` for clarity.
- Tolerance formula: `tol = max(abs_tol, rel_tol × scale)` where scale adapts to objective
  magnitude. Medicare gate (skip iteration 0 for convergence) correctly preserved.
- **Tests**: 5 tests in `tests/test_sc_convergence_helpers.py`.

#### ACA start year

- `aca_start_year`: Calendar year when ACA coverage begins. Years before this are treated as
  employer-covered (zero ACA cost). Default `0` = ACA applies from plan start.
- Documented in `PARAMETERS.md` and `modeling-capabilities.md`.
- **Tests**: 5 tests added for ACA start year.

#### Bug fixes

- **Correlation matrix**: Division by zero for constant-return series now handled correctly
  with masking; avoids inf/nan in rate model fitting.
- **SPIA annuitant lookup**: Typo in annuitant name now logged as a warning and row skipped,
  rather than silently misassigned to individual 1.

#### Scripts

- `owlplanner.sh` / `owlplanner.cmd`: Launcher script improvements - update on changes as opposed to cloud.

---

### Version 2026.04.27

- Improve detection of convergence anomalies in MC (issue#119).
- Upgrade requirement on gitpython to address vulnerability.

---

### Version 2026.04.21

#### Longevity risk in stochastic spending + parallel plan solving

- **Longevity risk** (MC-only, `with_longevity=True`): Each Monte Carlo scenario in
  `runStochasticSpending` can now independently draw ages-at-death from an actuarial mortality
  table, capturing joint market and longevity uncertainty. For couples the last-survivor horizon
  is used per scenario. Draws are seeded independently of the rate RNG for full reproducibility.
- **Five actuarial mortality tables** (`setMortalityTable`): `SSA2025` (default, general US
  population), `RP2014` (pension recipients), `IAM2012` (individual annuity purchasers, longest-
  lived), `VBT2015-NS` (non-smoking life insurance), `VBT2015-SM` (smoking life insurance).
  Sampled via `sample_lifespans(sex, current_age, n, rng, table)` in
  `owlplanner.data.mortality_tables`.
- **`plan.sexes` / `setSexes`**: Biological sex (`"M"`/`"F"`) per individual, required for
  mortality sampling. Defaults to `["F"]` (single) or `["M","F"]` (married).
- **Parallel plan solving** (`runMC`, `runHistoricalRange`, `runStochasticSpending`): Scenarios are
  now solved in parallel using `ThreadPoolExecutor`. HiGHS releases the GIL during solve, enabling
  real multi-core throughput. Worker count auto-sized to available CPUs. All randomness
  pre-generated in the parent thread for determinism independent of thread scheduling.
- **UI — Spending Optimization**: Longevity risk toggle, mortality table selector, and longevity
  seed control added. Summary line now includes the selected mortality table when longevity is on.
  Outcome chart and efficient frontier title reflect active scenario method.
- **Removed aliases**: `stochastic` and `histochastic` rate-method aliases removed; use `gaussian`
  and `histogaussian` (canonical names since v2026.03.05). `default` alias for `trailing-30` retained.
- **UI — Rates**: Random seed control and reproducibility toggle exposed directly in the UI.
- Fix short horizons and added edge tests
- Add spending-to-savings ratio in summaries
- Add savings retention curve over horizon to graphs
- Add Case_bill and test for simple depletion test - document discrepancies
- Fix textbox height in Create_Case to fit description
- Update documentation

---

### Version 2026.04.08

#### Stochastic spending optimization + stress-test refactoring

- **`runStochasticSpending`** (new): Collects per-scenario optimal spending bases across historical
  or Monte Carlo scenarios, then solves a stochastic recourse LP to find a committed first-year
  spending level $g^*$ that maximizes spending subject to a target shortfall probability. Sweeps a
  risk-aversion parameter $\lambda$ to trace the efficient frontier (committed spending vs. expected
  shortfall). Returns a dict with bases, lambdas, frontier arrays, and plan metadata.
- **`g_for_success_rate`** (new, public API): Returns $(g^*, \lambda)$ for the least conservative
  frontier point achieving a target success rate. Exported from `owlplanner`.
- **New plots** (both backends): `plot_spending_by_year` — bar chart of optimal spending/bequest by
  historical start year (plan-year dollars). `plot_stochastic_frontier` — success rate curve and
  efficient frontier side by side. `plot_stochastic_outcomes` — scenario bar chart colored by
  success/failure.
- **Stress-test refactoring**: `runHistoricalRange` and `runMC` extracted from `plan.py` into
  `src/owlplanner/stresstests.py` as module functions (`run_historical_range`, etc.) with `Plan` delegating methods.
  Public API unchanged.
- **Historical Range page**: When augmented sampling is off, a per-start-year bar chart is shown
  below the histogram.
- **New UI page**: *Spending Optimization* (`:material/query_stats:`) under Stress Tests. Scenario
  method radio (historical / Monte Carlo), target success rate slider, and an advanced options
  expander with roll and reverse sequence controls for historical mode.
- **Documentation**: Stress Tests section updated (three pages, new expander);
  `modeling-capabilities.md` Simulation modes row updated.

---

### Version 2026.04.07

#### SS claiming age optimization (`withSSAges`)

- **`withSSAges` solver option**: The MIP optimizer now selects the optimal Social Security claiming
  month per individual (age 62–70, 97 choices). Pass `"optimize"` for all individuals, a name or
  list of names for specific individuals, or `"fixed"` (default) to use ages from
  `setSocialSecurity()`.
- **Per-individual selection**: Useful for couples where one spouse has already claimed — pass that
  spouse's actual claiming age to `setSocialSecurity()` and optimize only the other. Individuals
  whose current age exceeds their recorded claiming age are always treated as fixed.
- **Formulation**: Own SS benefits co-optimized in the LP via a precomputed benefit table
  `B_own[i, k, n]` and binary claiming-month selectors `zssa[i, k]`. Spousal and survivor benefit
  offsets recomputed each SC iteration. Compatible with all other solver options.
- **UI (Run Options)**: New *Optimize SS claiming age* radio group. Age inputs on the Fixed Income
  page become read-only for optimized individuals; optimal ages written back after solving.
- **`plan.ssecAges`**: Optimal claiming ages after solving. `summaryDf()` / `summaryString()`
  include a *SS claiming age* line per individual with non-zero PIA (e.g. `"67y 03m"`).
- **`PARAMETERS.md`**: New `withSSAges` entry.
- **Tests**: 17 tests in `tests/test_ss_ages.py`.

---

### Version 2026.04.02

#### New objective: `maxHybrid` — blended spending and bequest

- **`maxHybrid` objective**: Blends spending and bequest into a single LP objective. Controlled by
  `spendingWeight` *h* ∈ [0, 1]: `h=1` maximizes spending only, `h=0` maximizes bequest only,
  `h=0.5` gives equal weight (both terms normalized to present-value dollars).
- **`spendingFloor`** (new): Hard lower bound on annual net spending (today's \$k) for `maxHybrid`.
  Recommended to prevent degenerate zero-spending solutions when growth rates are high.
- **`spendingWeight`** (new): Blend weight *h*; defaults to `0.5`.
- **`timePreference`** (new): Discounts future spending exponentially (%/year), shifting the optimal
  spending profile earlier. Supported for `maxSpending` and `maxHybrid`.
- **`spendingSlack` for `maxHybrid`**: Repurposed as a one-sided cap (spending ≤ floor × (1 + slack%));
  set to `0` (default) for no cap.
- **UI (Goals page)**: New *Hybrid* choice in the Maximize radio group with spending floor input and
  spending weight slider (0–1, step 0.05). Time preference slider in Spending Profile section
  (0–10 %/yr, step 0.5).
- **Schema**: `SolverOptions` gains `spendingWeight`, `spendingFloor`, and `timePreference`.
- **Docs**: `PARAMETERS.md`, Documentation (Goals expander), `modeling-capabilities.md`
  (Objectives and Spending profile rows) updated.
- **Tests**: 13 tests in `tests/test_hybrid_objective.py`.

---

### Version 2026.03.29

#### Worksheets: age columns, real-dollar display, and solver time limit

- **`worksheet_show_ages`**: Age columns now included in the saved Excel workbook (not just
  on-screen). Final balance row carries the correct age; blank beyond the individual's horizon.
- **`worksheet_real_dollars`** (new): Divides all currency values by the cumulative inflation factor
  $\gamma_n$, converting nominal to today's dollars in both on-screen tables and the saved workbook.
  Saved filename gains a `_real` suffix. Toggled on the Worksheets page; round-tripped in TOML.
- **`worksheet_hide_zero_columns`**: Clarified as display-only; saved Excel retains all columns.
  Age columns protected from zero-column filtering.
- **Worksheets page**: Expander renamed to *Table display and save options*; real-dollars toggle added.
- **Default solver time limit**: `maxTime` default reduced from 900 s to 180 s, leveraging
  SC-loop warm-starting to cut total solve time on hard MILP cases.
- **Docs**: `PARAMETERS.md` (`[results]` table and example TOML); Documentation (Worksheets).
- **Tests**: 9 new tests in `tests/test_export.py`.

---

### Version 2026.03.26

#### Breaking change: HFP person sheets require all columns

- Each person worksheet must include every time-horizon column: `year`, `anticipated wages`,
  `other inc`, `net inv`, `taxable ctrb`, `401k ctrb`, `Roth 401k ctrb`, `IRA ctrb`,
  `Roth IRA ctrb`, `HSA ctrb`, `Roth conv`, `big-ticket items`. Omitting a column is an error.
- Clearer `ValueError` listing missing headers; legacy `other inc.` still normalized.
- All `examples/HFP_*.xlsx` workbooks and `HFP_template.xlsx` updated.
- **Docs**: `PARAMETERS.md` HFP section; Documentation (Financial Profile) aligned.
- **Tests**: `tests/test_timelists.py` expects errors for missing required columns.

---

### Version 2026.03.24

#### Worksheets: optional ages and hide-zero columns

- **`worksheet_show_ages`** and **`worksheet_hide_zero_columns`** (new `[results]` options,
  default `false`): round-tripped in TOML.
- **Worksheets page**: *Table display options* expander with both toggles.
- **Show ages**: Per-person age columns (integer, Dec 31 of each year); blank beyond horizon.
  On-screen only — saved Excel unchanged.
- **Hide all-zero columns**: Drops numeric columns where every value is zero; `year` never dropped.
  On-screen only.
- **Docs**: `PARAMETERS.md` (`[results]` table and example TOML); Documentation (Worksheets).
- **Tests**: `tests/test_worksheet_display_utils.py`.

---

### Version 2026.03.12

#### Medicare Part D

- Part D premiums (IRMAA surcharges, same MAGI brackets as Part B) now included by default.
- `medicarePartDBasePremium`: optional monthly base premium per person (default `0`).
- `includeMedicarePartD` solver option (default `true`); set `false` for other drug coverage
  (employer plan, VA, etc.).
- Schema, `PARAMETERS.md`, `modeling-capabilities.md`, `owl.tex`, and Run Options UI updated.

---

### Version 2026.03.11

#### Decomposition fixes

- Benders: skip zm pre-fixing when both individuals are already on Medicare at plan start;
  prevents SP LP infeasibility on later iterations.
- Benders: gap check and stall-detection added after the master MIP step.

---

### Version 2026.03.10

#### LTCG and NIIT exact MIP formulations

- **`withLTCG="optimize"`**: Binary variables (`zl`) replace the SC-loop heuristic for LTCG
  bracket assignment, giving provably correct long-term capital gains tax rates.
- **`withNIIT="optimize"`**: Binary selection (`zj`) on whether MAGI exceeds the \$200k/\$250k
  NIIT threshold. Most effective combined with `withLTCG="optimize"`.
- Both modes exposed as expert toggles in the UI (Advanced Options).
- **Tests**: `tests/test_ltcg_lp.py` (6 tests) and `tests/test_niit_milp.py` (6 tests).

#### MIP decomposition (`withDecomposition`)

When multiple `"optimize"` flags are active simultaneously, the monolithic MIP can be slow
(~400 binaries for a typical two-person plan). Two strategies are available:

- **`"sequential"` (relax-and-fix heuristic)**: LP relaxation → round and fix bracket families
  one at a time (`zl → zs → zj → zm → za`) → solve reduced MIP. Fast but not globally optimal.
- **`"benders"` (certified global optimum)**: Classical Benders decomposition — bracket-selection
  binaries in the master MIP, continuous planning in the subproblem LP/MIP. Dual-based optimality
  cuts certify global optimality. Converges in 1–3 iterations in practice. HiGHS and MOSEK supported.
- **`"none"`** (default): monolithic MIP (unchanged).
- `bendersMaxIter` option (default 50) caps Benders iterations.
- **Tests**: 11 tests in `tests/test_decomposition.py`.

#### HiGHS direct API

- HiGHS is now called directly via `highspy`; the `scipy.optimize.linprog` proxy is removed.
- **PuLP/CBC and PuLP/HiGHS removed**: only HiGHS (direct) and MOSEK are supported.
- `abcapi.py`: `ConstraintMatrix.to_csr()` returns HiGHS rowwise CSR format. Warm-start via
  `_highs_warm_start`.

#### `owlcli`: schema-driven solver options

- `SolverOptions` Pydantic model in `schema.py` is the single source of truth; used by TOML
  load, `plan_bridge`, and the CLI.
- **`--help-solver-options`**: Parses `PARAMETERS.md` at runtime — always in sync with docs.
- **`--solver-opt KEY=VALUE`**: Override any solver option on the command line.
- **Solver choices**: `--solver` now accepts only `default`, `HiGHS`, and `MOSEK`.

#### UI and configuration

- Run Options: expert toggles for *Optimize LTCG brackets* and *Optimize NIIT*; *MIP decomposition*
  radio (`none` / `sequential` / `benders`).
- `withDecomposition` wired through `config_to_ui` / `ui_to_config`; legacy boolean `True` coerced
  to `"sequential"`.
- **`PARAMETERS.md`**: `withDecomposition` and `bendersMaxIter` entries added.

---

### Version 2026.03.09

#### ACA marketplace (pre-65) UI exposure

- **Run Options**: New *ACA Marketplace (Pre-65)* section with SLCSP benchmark premium input.
  *Optimize ACA (expert)* toggle in Advanced Options (enabled only when SLCSP > 0).
- Config/UI bridge: `aca_settings` and `withACA` wired through `config_to_ui`, `ui_to_config`,
  and `genDic`.
- **Example**: `Case_morgan` illustrates ACA modeling for a pre-65 retiree.
- **Documentation**: ACA added to the self-consistent loop description.

#### HSA accounts (fourth savings account type)

- HSA balances tracked alongside taxable, tax-deferred, and tax-free accounts (`j=3`).
- Pre-tax contributions reduce ordinary income, SS provisional income, and MAGI. Contributions
  zeroed at Medicare enrollment age (IRC §223). All withdrawals treated as qualified (tax-free).
- Non-spouse heirs include the full HSA balance in ordinary income (IRC §223(f)(8)(B)); bequest
  discounted accordingly.
- `setAccountBalances(hsa=...)` and `setHSA(balances, medicare_ages)` convenience method.
  Account allocation, asset composition, and Fixed Income page updated.
- **Tests**: 9 tests in `tests/test_hsa.py`.

---

### Version 2026.03.07

#### `"net inv"` column in HFP

- New optional `net inv` column (net investment income from rent or trust distributions) in the
  Wages and Contributions spreadsheet. Enters cash-flow, taxable-income, SS-taxability, and MAGI
  constraints; counted in NII for NIIT. Backward compatible (defaults to zero when absent).
- `"net inv"` appears in each individual's Sources sheet in the workbook.

#### Pension survivor benefits

- **Joint-and-survivor (J&S) option**: Surviving spouse receives a configurable fraction (0–100%)
  of the primary's pension after death. Config: `pension_survivor_fraction`; UI: Fixed Income page.

---

### Version 2026.03.05

#### Rate models

- **`lognormal`** (new): Correlated log-normal with user-specified arithmetic means, volatilities,
  and correlations. Returns bounded below −100%, consistent with Geometric Brownian Motion.
- **`histolognormal`** (new): Fits a correlated log-normal to the selected historical window.
  History-grounded alternative to `lognormal`.
- **`var`** (new): VAR(1) model fitted by OLS on a historical window. Captures year-to-year serial
  correlations across all four asset classes; optional spectral shrinkage for stationarity.
- `bootstrap_sor` and `var` now exposed in the Rates Selection and Monte Carlo pages.
- **MC guard fix**: `runMC()` uses `rateModel.deterministic` attribute instead of a hardcoded name
  check.

#### Rates Selection UI redesign

- Constant-preset and varying-method selectors are now `st.selectbox` widgets with a concise
  description caption surfaced from each model's metadata.

#### Bug fixes

- `reverse_sequence` and `roll_sequence` were silently ignored in non-augmented historical range
  runs; both now read from session state and passed correctly.
- Run Options page warns when the minimum balance constraint may cause infeasibility.
- **Rename**: *Simulations* → *Stress Tests* throughout.

#### Tests

- `test_rate_model_var.py`: 24 tests (shape, reproducibility, fitting, Cholesky, shrinkage,
  parameter validation, reverse/roll, MC integration).

---

### Version 2026.02.24

#### HFP (Household Financial Profile)

- **Optional `"other inc"` column**: Other ordinary income (consulting, royalties, etc.) in the
  wages and contributions table. Backward compatible; `scripts/add_other_inc_column.py` migrates
  existing files.
- **Reports page**: Warning shown when HFP values were edited in the UI (case file alone cannot
  reproduce the run).

#### Configuration

- Case-insensitive `case_` prefix check when saving TOML (issue #96).

#### Code organization

- `pension.py` and `spending.py` extracted from `plan.py`. SS tax logic moved to `tax2026.py`;
  `setSocialSecurity` logic to `socialsecurity.py`; gamma/rate transforms to `rates.py`;
  oscillation detection to `utils.py`.

---

### Version 2026.02.23

#### Social Security accuracy

- **Dynamic SS taxability fraction**: `Psi_n` now computed each SC iteration from the IRS
  provisional income formula (MFJ: \$32k/\$44k; single: \$25k/\$34k) with 30% damping for
  convergence, replacing a fixed 85%. Retirees with lower income get more accurate (lower) SS taxation.
- **`withSSTaxability`**: Pin `Psi_n` to a fixed value in [0, 0.85] (replaces `tax_fraction`
  parameter to `setSocialSecurity()`).
- **FRA table fix**: `getFRAs()` now returns the correct Full Retirement Age for birth years
  1938–1942 (65+2/12 to 65+10/12 per SSA table).

#### SS trim

- `social_security_trim_pct > 0` without `social_security_trim_year` now raises an error instead
  of silently defaulting to 10 years from now.
- SS trust-fund exhaustion default changed to 2033 (SSA Trustees Report projection).
- "Starting year" widget greyed out when reduction percentage is 0.

---

### Version 2026.02.20

#### UI

- **Create Case redesign**: Three columns (create, upload, load example) when no case is active;
  collapsible expander when a case is already loaded.
- **Inline HFP uploader**: After case creation, an HFP upload widget appears directly on the
  Create Case page.
- **Streamlit compatibility**: Version pin and `altair < 5` restriction removed from
  `requirements.txt`.

---

### Version 2026.02.19

#### Rate models

- **`BuiltinRateModel` decomposition**: Single dispatcher replaced by 8 concrete `BaseRateModel`
  subclasses. `BuiltinRateModel` shim preserves backward compatibility.
- **Stochastic UI fix**: Builtin rate model now accepts config-style parameter names
  (`standard_deviations`, `correlations`) in addition to API names.
- **`getRatesDistributions`** (issue #92): Returns percent by default; accepts optional `df=`
  parameter for user-supplied DataFrames.
- **DataFrame rate model** (issue #92): Column names standardized (T-Notes/T-Bills); `in_percent`
  parameter replaces heuristic; display names aligned with column names.
- Rates UI: label `'fixed'` renamed to `'constant'`.

#### Social Security

- SS trim (reduction from a given year onward): config, schema, UI bridge, and Fixed Income page.

---
