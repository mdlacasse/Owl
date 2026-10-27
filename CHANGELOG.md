### Version 2026.10.26

#### Fixed: a worker's earnings charged against a spouse past full retirement age use the adjusted benefit

When a worker still under full retirement age has excess earnings and their spouse, collecting a
spousal add-on on the worker's record, has passed it, the excess is charged against that add-on.
From the spouse's FRA month the add-on is the one raised by the adjustment of the reduction
factor, but **Owl** charged the unadjusted one and then scaled what was left, so dollars were
neither paid nor withheld: in the case of #232, paid plus withheld fell short of the benefits due
by \$810.11 (worker earning \$60,000) and \$1,381.31 (\$70,000) in a year. The excess is now
charged a second time on the adjusted benefits, after the crediting months have been counted from
the months before FRA, which the second charge leaves unchanged.

#### Fixed: the earnings test's exempt amounts and the payroll wage base are read in the plan's dollars

The exempt amounts are published in each year's nominal dollars, but the earnings test compared
them with earnings in the plan's first-year dollars, and for a year after the table used the last
year's nominal amount as if it were in those dollars. That held only for a plan starting in 2026.
A plan starting in 2027 used 2026's \$24,480 for 2027, and withheld \$540 too much on \$40,000 of
wages ((40,000 − 24,480)/2 against (40,000 − 25,560)/2). Each published amount is now deflated by
its year's inflation factor, and held flat in real terms after the last one. The 2027 amounts
(\$25,560 and \$67,920, SSA notice of Oct. 26, 2026, 91 FR 67380) are added: a plan starting in
2026 now withholds the same for 2027 as one starting in 2027. The Social Security wage base of the
payroll tax, a single value held at its 2026 level in today's dollars, is now keyed by year the
same way, with 2027's \$192,300 from the same notice: at 2.5% inflation, wages above the base in
2027 pay \$197.63 more than under 2026's base grown with inflation. A plan starting after the last
published year takes that year's amounts as its own dollars, an understatement, and warns.

#### Fixed: pay that all goes to a 401k is still payroll-taxed earnings

*Anticipated wages* are net of pre-tax contributions, and the earnings that the payroll tax and
the SSA earnings test read added the year's 401k and IRA contributions back only in a year with
wages. Pay deferred in full into a 401k, as part-time pay can be at the catch-up limits, carried
neither tax nor test, and one dollar of wages switched both on for the whole deferral: \$1,798 of
payroll tax on \$23,500 deferred. A 401k elective deferral is wages for both (26 U.S.C.
3121(v)(1)(A)), so it now counts with or without other wages. An IRA contribution still counts
only in a year with pay, the 401k's included: without pay it is taken as a spousal IRA, funded
by the other spouse. The *401k ctrb* column is kept apart from *IRA ctrb* for this, and a
workbook saved from a plan now writes both columns instead of their sum under *401k ctrb*. In
the assistant's tools, a traditional IRA contribution is the new account `"ira"`;
`"tax_deferred"` is the employee's deferral to an employer plan (401k/403b). An account the
tools do not recognize is now refused rather than taken as tax-deferred, where a mistyped Roth or
HSA contribution would have counted as payroll-taxed earnings.

#### New: an *employer ctrb* column for the employer's 401k contributions

The employer's match or profit-sharing contribution had to be entered in *401k ctrb*, beside the
employee's own deferral, and was therefore counted as earnings, raising the payroll tax by 7.65%
of it (\$382.50 on a \$5,000 match) and the earnings it tests. It was never wages (26 U.S.C.
3121(a)(5)(A)). The new HFP column *employer ctrb*, and the assistant's account `"employer"`, put
it in the same tax-deferred account but leave it out of the earnings. A workbook without the
column reads it as zero, which keeps its previous meaning, so its absence is not reported; move
the employer's share out of *401k ctrb* to have it left out. The template carries the column.

#### Fixed: branch-and-bound loops that never settled, although their parameters had

Branch-and-bound returns any plan within its gap of the optimum, 0.3% when Medicare is solved as
MILP. When the self-consistent loop changed the problem by a few dollars, MOSEK returned a
different plan along a direction where the objective is nearly flat (Case_jack+jill: \$3k to
\$120k of taxable withdrawals moving among 2036-2038 every iteration), and the loop's test, a
change in objective 60 times finer than the gap, could not be met: jack+jill, avery+quinn and joe
ran to the 30-iteration limit. The fed-back gain fraction was not the cause; it settles in three
iterations once the plan stops moving. Each branch-and-bound solve now re-solves the LP with the
previous iteration's binaries and keeps them when they tie the new plan, within the loop's
relative tolerance: the noise goes, and nothing worse than the new plan is kept. Convergence is
judged on what is fed back: the gain fraction joins the residual, an exact NIIT leaves it (it is
not fed back), and a change in objective below the solve's own gap no longer holds the loop. On
the 18 examples measured under MOSEK, jack+jill settles in 4 iterations (from 30) and 15 s (from
105 s) with no residual, joe in 4 (from 30), avery+quinn in 7 (from 30) and 45 s (from 189 s) at
the same value, alex+jamie gains \$66 in 2 iterations, and the other 14 are unchanged; total
time 677 s -> 415 s. Under HiGHS these cases already settled in 3 to 5 iterations and stay within
a few dollars. Local search is not affected.

#### Changed: the Summary has the same rows for every plan, so variants compare row for row

The side-by-side comparison keeps only the rows all its cases share, and several Summary rows were
reported only when nonzero: *Total fixed income* and each of its lines (Social Security, pension,
SPIA, wages, other income, fixed assets), *SS withheld by the earnings test* and *ARF months*,
*Total qualified charitable distributions* and the RMDs it satisfies, *Total state income tax
paid*, and each person's *SS claiming age*. A row one variant lacked vanished from the comparison
of all of them: Case_jordan+taylor-qcd, built to be compared with Case_jordan+taylor, lost its QCD
rows, and retiring now lost *Wages*. They are now always there, at \$0 or "none" (a claiming age
reads "none" for a person with no benefit of their own and no spousal one). Rows set by the plan's
shape still vary: the people's names, the partial bequest when the first death falls inside the
plan, and the final bequest on a summary shorter than the plan.

#### New: the employee's payroll tax is paid on wages

*Anticipated wages* count as cash, and **Owl** charged no payroll tax on them, so each working
year brought in 7.65% more cash than it does. Every solve now charges the employee's share on the
earnings the SSA earnings test reads (*anticipated wages* plus the year's 401k and IRA
contributions): 6.2% social security tax on each person's earnings up to the wage base (\$184,500
in 2026, held at that level in today's dollars), 1.45% Medicare tax on all of them, and the 0.9%
Additional Medicare Tax on the household's combined earnings above \$250,000 through the year of
the first death and \$200,000 after (not indexed). The tax is not deductible: it is a constant of
the year's cash-flow balance, next to debt payments, with no variable, constraint, or binary, and
it enters no income-tax computation, `T_n` or the effective tax rate. There is no option. It is
reported as *Total payroll tax paid* in the Summary (\$0 for a case without earnings, so plans
compare row for row), a *payroll tax* column of the Cash Flow and Taxes worksheets and the CSV
export, in *Tax bills + Med.* of the Income worksheet, as `payroll_tax_today` /
`payroll_tax_nominal` in the plan metrics that `owlcli compare` reports, and on its own, beside
the income tax rather than inside it: a *payroll tax* line in the taxes plot (now titled *Taxes and
Premiums*), and a *Payroll tax* slice and band in the lifetime allocation and the annual cash-flow
mix.
Self-employment tax is not modeled (a documented limitation). The twelve examples without wages
are unchanged to the cent. The seven with wages pay \$3,672 to \$100,138 over their working
years: alex+jamie, chris+pat, jack+jill, joe, jon+jane and riley+casey spend \$242 to \$5,156
a year less (0.2% to 3.2%), and john+sally's bequest goes from \$16,803 to \$21. That last case
had little to spare: its \$8,798 of tax, compounded to the horizon, costs \$17,300 of bequest, so
in loop mode the bequest reaches zero at 97% of the tax, after which the loop ends on a plan that
undercharges IRMAA by \$374 (its fixed-point residual). Local search gives \$31,778 without the
tax and \$14,013 with it, both with no residual, so john+sally's reproducibility pin now solves it
under local search, a `deep` test (\$14,013), instead of pinning the loop's \$21. The tax leaves john+sally no room for the moves
of #197, so its two local-search tests now solve the case without it: one checks that the search
reaches the branch-and-bound plan (31,778; 30,823 with the full LTCG link rows), the other that
step (b') matters on its own (30,823 with the full rows; 20,004 without it either), which the first
test did not show. The filing status of each year (joint through the year of the first death and
single after) is now one function, `filingStatusIndex_n`, in place of eight copies of that rule in
the federal brackets, the gains tax and its rows, the NIIT and its rows, the taxability of Social
Security and its rows, and the state brackets; the payroll tax reads it too. The standard deduction
and the senior bonus (`taxParams`, `seniorBonusSchedule`) keep their own, where the same death also
removes the deceased from the people counted. Every pinned plan is unchanged. Thanks to Florin
Mateoc (@fmateoc) for the issue and the PR (#227).

### Version 2026.10.25

#### Fixed: branch-and-bound no longer keeps a plan that charges a cost its own income does not imply

Branch-and-bound stops at a relative gap, 3e-3 when Medicare is solved as MILP, and a plan inside
that gap can charge a threshold cost its own income contradicts. In Case_robin (MOSEK) it taxed
85% of Social Security in 2042 and 2045, years whose provisional income is below the base amount:
\$1.6k of federal tax a year not owed, \$47,323 of SS residual over the plan. After each
branch-and-bound solve, the years where the plan's own income implies a different cost than the
one charged are now solved again, every family's binaries free in those years and pinned in the
others, and the result is kept when it is better: the step local search already takes. The
problem contains the plan it repairs, so it cannot return a worse one. Across 18 of the 19
examples (MOSEK; riley+casey runs past 40 minutes either way), robin goes to a \$0 residual for
\$67 a year more spending (0.15%), chris+pat, morgan and jon+jane gain \$12 to \$43 and keep
at most \$18 of residual, 13 are unchanged, and each repair takes a tenth of a second. The two
cases whose cost basis keeps the loop from settling (avery+quinn, jack+jill) still stop at the
iteration limit, within \$6 of the same value. The default gap stays: at 1e-4, plans gain up to
0.08% more where nothing is inconsistent (alex+jamie, dana), for up to 24 times the run time.

#### Fixed: a mixed-integer plan can no longer pay a lower IRMAA tier than its MAGI

A solver accepts a binary within its integrality tolerance of 0 or 1, about one millionth. Times
a bracket's big-M, the year's income ceiling in the tens of millions, that let a few dollars into
a bracket whose binary counted as off: in Case_jordan+taylor under local search, IRMAA's top tier
held \$17 to \$287 of MAGI, so years a few dollars past a tier edge paid the tier below, and the
plan's premiums were \$2,300 to \$3,470 a year lower than its own MAGI implies (\$63,522 of IRMAA
residual over the plan). After every mixed-integer solve (branch-and-bound, local search, and
the solves around them, with either solver), the binaries are now rounded and the plan re-solved
as an LP with them pinned, which closes every such bracket exactly; the re-solve is skipped when
the binaries are already exact. Across the 19 examples under local search, jordan+taylor's
residual goes to \$0 for \$66 less bequest (0.004%), three others lose a few dollars of hidden
residual, and the other 15 are unchanged, at the same run time. Under branch-and-bound,
jordan+taylor's \$4,593 residual goes too, and both methods now give the same plan.

#### New: Case_riley+casey, bridging to Medicare on the ACA in Georgia

A married couple, 62 and 54, in a state without the Medicaid expansion, with most of their savings
in high-basis taxable accounts. It gathers rules no other example reaches: the Social Security
earnings test's grace year (Riley claims in July after six months of part-time work, so nothing is
withheld; without *months worked*, \$9,876 would be), Roth 401(k) contributions paid from pay with
their big-ticket offset (#221), an HSA contribution from savings deducted through a negative
*other inc* (#225), and ACA pricing with the coverage gap and the 400% cliff (#202). It ships in
loop mode, like the other examples, and costs about a second in the test suite. In loop mode it
spends \$116,758 a year and pays the full benchmark in 2026-2028; local search prices the cliff
exactly and spends 2% more for \$58k less in premiums. The docs now also say that in the year
Medicare starts, an HSA deduction entered as a negative *other inc* covers only the months before
it, the share of the contribution **Owl** keeps.

#### Tests: slow quality checks run on demand

A `deep` marker holds checks of solution quality that take minutes, left out of the default run,
CI included (`pytest.ini`): run them with `pytest -m deep` or `make tests-deep` when changing an
algorithm or a feature they cover. They are the riley+casey comparison of loop and local search,
the two-spouse claiming-age search, the #197 reach of local search, and local search through the
MCP tools. The local-search fixture of `test_local_search.py` now runs with a 30 s budget: its
tests hold whatever the search reaches, and with HiGHS it spent the whole 300 s default.

#### Fixed: falling back on an earlier iterate takes the most settled one, not the richest

When an iterate of the self-consistent loop cannot be solved even with a shortened parameter
step, the loop falls back on an earlier one. It took the one with the best objective. On a tight
case the costs the loop feeds back (premiums, ACA costs, NIIT, the taxable part of Social Security,
LTCG bracket room) start at nothing and catch up pass by pass, so the best objective belongs to the
iterate least charged for what its own income brings: a case heading from \$6.6M down to a few
thousand dollars reported \$1.1M, and a lower spending floor could report less left at the end
than a higher one. The fallback now takes the iterate whose own income moves its parameters least,
the latest of those tied, and every iterate's residual is kept in the trace. Thanks to Dmitry
Fink (@finik) for the diagnosis and the fix (#186).

#### Documented: the stacked capital-gains tax can exceed the worksheet's line 25 by up to \$57 a year

The Qualified Dividends and Capital Gain Tax Worksheet ends with the lesser of the stacked tax
and the regular tax on all taxable income (line 25, IRC 1(h)(1)). **Owl** keeps the stacked tax.
They differ only for gains between the 0% breakpoint and the top of the 12% bracket, which pay
15% there instead of 12%: at most \$28.50 (single) or \$57 (joint) a year, and \$0 in every one of
the 18 examples. The limitation is now documented. Taking the minimum exactly would need a binary
per year, at a solve-time cost out of proportion with the stakes. Thanks to Marco Pignone
(@rationalpiper) for pointing it out, with the worksheet and the bound (#206).

#### Fixed: an LP that HiGHS ends without a verdict is solved again before it is called a solver failure

HiGHS's default LP path (presolve, then the dual simplex) can stop on an LP that has no feasible
point with "Solve error", "Unknown" or no status at all ("Not Set"), instead of "Infeasible".
**Owl** then reported a solver error for a plan that simply cannot be paid for. On LPs that SCIP's
exact (rational) mode proves infeasible, HiGHS 1.15.1 and its `latest` branch gave a verdict on 2
of 62 (https://github.com/ERGO-Code/HiGHS/issues/3418). Such an LP is now solved once more with
the interior-point method and presolve off, which said "Infeasible" on all 62. The re-solve runs
only for a pure LP that ends with one of those statuses and without a feasible point, so every LP
that solves today comes out the same; MIPs, limits and interrupts are untouched. It replaces the
fallback of #184 (reverted), whose primal-simplex step could call a feasible LP infeasible, and
takes in #188. Thanks to Dmitry Fink (@finik) for tracking the failures down to HiGHS, with SCIP's
exact verdicts, the upstream report and the fix (#184, #188, #226).

#### Fixed: wages are entered as they enter AGI, and an after-tax contribution is paid for by a big-ticket item

**Owl** asked for *anticipated wages* net of every contribution column, because contributions are
deposited without leaving the cash flow. But the same wages are the taxable wages, and an
after-tax contribution paid from pay (Roth 401k, Roth IRA, taxable) is still income: netting it
out dropped it from AGI, from federal and state tax, and from the MAGI used for IRMAA, the ACA
and Social Security taxation, by the full contribution (\$4,400 of federal tax on \$20,000 of Roth
401k out of \$100,000 of pay). PARAMETERS.md meanwhile described a third convention. All the
documentation now gives the one that gets both tax and cash right: *anticipated wages* are the
wages in AGI, pay minus pre-tax 401k/403b, deductible IRA and payroll HSA contributions; each
contribution goes in its column; and each after-tax contribution paid from pay is paid for by a
negative *big-ticket items* entry of the same amount. With only pre-tax contributions nothing
changes. The SSA earnings test, which counts wages before pre-tax deferrals, now adds back only
the tax-deferred contributions. The MCP tools and the intake checklist say the same. Of the
examples, only jon+jane had an after-tax contribution from pay, \$2,000 a year into taxable
savings in 2026-2030: its workbook now enters \$122,000 of wages and \$-2,000 of big-ticket items
in those years, which adds \$1,993 to the 2026 MAGI and \$440 to that year's federal tax, and
lowers spending by \$148 a year (0.09%). Thanks to Marco Pignone (@rationalpiper) for the report
and for the convention (#221).

#### Fixed: a Roth conversion is free from the fifth year after it, and its own year cannot release earnings

A conversion's 5-year period is five taxable years starting with the year of the conversion (IRC
408A(d)(3)(F)), so a 2026 conversion can be withdrawn without the 10% from 2031. **Owl** held it
back a year more, through 2031, so a conversion ladder reached each rung a year late and paid the
10% on tax-deferred withdrawals in the meantime (#224). The early-withdrawal rows of #209, on the
other hand, counted every conversion made so far as withdrawable before 59½, the year's own
included: a plan could convert an amount and withdraw the same amount from a Roth holding only
earnings, which the ordering rules (conversions oldest first, then earnings, 408A(d)(4)(B)) charge
the 10%, and **Owl** charged nothing (#223). Both now follow the rules: a conversion is held through
the year of the conversion and the four after it, and before 59½ only conversions past that period
count toward what can be withdrawn. In the reported ladder, the 10% paid before 59½ falls by
\$2,113 and spending rises by \$79 a year, with nothing the law charges left uncharged; in the
reported recapture case, the \$748 of 10% that went uncharged is gone. Of the examples, jack+jill's
bequest rises by \$57; Case_morgan used the same-year route (\$567 of 10% uncharged) and no longer
does, at a cost of \$70 a year of spending when solved exactly (its self-consistent loop lands
elsewhere, 1.1% higher). Thanks to Marco Pignone (@rationalpiper) for both reports, with the
statute, the Form 5329 instructions, the repros and the fixes (#223, #224).

#### Fixed: HSA contributions entered through the MCP tools stop at Medicare

An HSA contribution read from the HFP stops at Medicare enrollment, the year it starts keeping
the months before it, but one entered through the MCP tools' `contributions` was deposited every
year it was listed, Medicare or not. The tools now apply the same cut. A workbook rebuilt from a
plan's arrays (by `save_case`, or when saving a plan whose arrays were set directly) holds the
amount entered rather than the share kept, so reading it back applies the cut once.

#### The MCP tools take other income, so an assistant can enter an HSA deduction

Every MCP tool that builds a plan from parameters (`run_from_params`, `save_case`, the
stochastic and comparison tools) now takes `other_income`, the HFP *other inc* column: signed
annual amounts, a negative one being an above-the-line deduction paid from cash. Without it an
assistant could not enter the deduction for an HSA contribution made without wages (#225), nor
any other ordinary income outside wages. The intake checklist asks about it, and `save_case`
writes it to the HFP.

#### Fixed: an HSA contribution without wages can now be deducted, by entering a negative *other inc*

An HSA contribution is deducted above the line whether or not there are wages (IRC 223(a),
62(a)(19)), and since 2026 every bronze exchange plan qualifies, so early retirees on the ACA can
contribute from savings and lower the MAGI their credit is figured on. **Owl** only deducted a
contribution netted out of *anticipated wages*: without wages there was nothing to net it from,
the HFP rejected a negative amount, and the *HSA ctrb* column alone deposited the money without
deducting it or paying for it. *other inc* now accepts a negative amount, an above-the-line
deduction paid from cash: enter the contribution in *HSA ctrb* and the same amount as a negative
*other inc*. A deduction larger than the year's income is lost rather than making the plan
infeasible: taxable income stops at zero in the federal and state bases (in PA, which leaves
conversions out of state income, an \$8,000 contribution beside a \$30,000 conversion made every
mode infeasible), and in optimize mode an ACA or IRMAA MAGI below zero stays in the bottom
bracket. The reported MAGI is then below zero too, the MAGI those brackets priced, while taxable
income stays at zero. Cases with no negative entry solve exactly as before. The documentation now says which
columns may be negative (*other inc* and *big-ticket items*) and how an HSA contribution reaches
AGI, and no longer says that the year Medicare starts is zeroed: it keeps the months before.
Thanks to Marco Pignone (@rationalpiper) for reporting it, with the references, and for testing
the route (#225).

#### New: the Social Security earnings test

**Owl** paid Social Security in full to anyone claiming before full retirement age while still
working. SSA withholds \$1 for every \$2 of earnings above the annual exempt amount (\$24,480 in
2026), or \$1 for \$3 above the higher amount (\$65,160) in the months before FRA in the FRA year,
and pays the withheld months back from FRA by adjusting the reduction factor. The test is now
applied to the benefit streams before they reach the optimizer: the excess is charged month by
month against everything paid on the worker's record, the spouse's benefit included, then against
the spouse's own benefit; non-service months of the initial grace year are paid; and the reduction
factor is recomputed at FRA on each record. For a given claiming age these are fixed numbers, so
the model has no new variable, constraint, binary or loop quantity, and `withSSAges` sees the test
in every candidate. The earnings it counts are the wages before pre-tax deferrals: *anticipated
wages* plus that year's tax-deferred contributions, which those wages are entered net of (an
employer contribution makes them slightly high; HSA contributions stay out). A new
optional column, *months worked*, says how much of the year was worked (12 when absent): it decides
the grace year, the year someone stops working and claims, where the months after work are paid;
the MCP tools take it as `months_worked`.
The Summary reports *SS withheld by the earnings test* and *ARF months* for a household with
earnings the test can reach, the per-person worksheets a *SS withheld* column, and `owlcli explain`
an `earnings_test` block. Survivor benefits are left out: checks from the year of the first death
on are paid as before. A case without earnings before someone's FRA is unchanged; of the examples,
alex+jamie (−0.24%), chris+pat (−0.19%) and jack+jill (+0.08%, the withheld months returning for
life) change. Thanks to Florin Mateoc (@fmateoc) for raising it with the SSA sources, for the
design, and for the implementation (#220, #222).

#### Faster local search, keeping the #197 fix

The fix for #197 freed the LTCG binaries in every round of the search's Social Security step,
which made local search up to 1.7x slower (4x with MOSEK). Most of that cost came from one half
of the LTCG link rows, "binary at 0 means ordinary income at or above the threshold": it is
redundant for the optimum, since a binary at 0 only closes the bracket below, but once pinned it
held income above a threshold that the better plan needed to cross. The search now relaxes that
half in its own copy of the problem, pins the LTCG binaries in the SS step again, and frees them
alongside the SS step once per loop iteration, only when the rounds stall. Branch-and-bound keeps
the full rows: without them, one example ran 23x slower. Before returning, the search sets back to 1
every binary left at 0 below its threshold, so that the repair, polish and dual solves stay
feasible. On the 18 examples: local search takes 45% less time with MOSEK (726 s to 396 s) and 6%
less with HiGHS (740 s to 695 s). Case_john+sally still reaches the branch-and-bound plan, and
every other example is within 0.07% (Case_morgan −0.066% and Case_kim+sam-bequest −0.028% with
MOSEK; Case_chris+pat +0.068% with HiGHS).

#### Fixed: the Roth conversion regret sweep can no longer report a negative regret

Pinning a scenario's first-year conversion restricts its unconstrained problem, so regret
cannot be negative. But a baseline solve could stop short of a plan its own sweep found
(local search carries no certificate, and the tax loop can settle on another fixed point),
and every cell above that baseline then read below zero. Each scenario's baseline is now
raised to the best plan of its sweep, pinned or never-convert, with its first-year
conversion, so the regret is non-negative by construction. The solves' own values and
conversions are kept as `v_star_solved` and `x_star_solved` (an automatic grid is still sized
from them), and the amount raised as `v_star_lift`. The lift still counts as the method's
error: the largest one enters the resolution floor, and the summary reports how many
baselines were raised and by how much (`baseline_lift`). `summarize_conversion_regret` lifts
sweeps saved before this change, and `lift_regret_baselines` does it for any saved result.
Lifting removes the sign error but not the shortfall: a baseline can still sit below the true
optimum by more than its best pinned plan reveals.

#### Fixed: an unused standard deduction now lowers the tax on capital gains

**Owl** stacked long-term gains and qualified dividends on top of ordinary taxable income, so when
ordinary income was below the standard deduction, the unused part was lost and the gains were taxed
as if it did not exist. The law taxes gains on taxable income after all deductions (Qualified
Dividends and Capital Gain Tax Worksheet, lines 1 and 10; IRC 1(h)(1)(B)), so the unused deduction
shields gains from the bottom up. This is the common early-retiree year spent living off a taxable
account: the overstatement reached 15% or 20% of the unused deduction, \$2,723 for a single
66-year-old in 2026. Both modes now widen the 0% and 15% gains brackets by the unused deduction,
including the senior bonus when it is optimized, and the LTCG residual check follows the worksheet.
In the test cases affected, the lifetime overstatement of \$10,000–\$26,000 falls to a few dollars,
and spending rises by 0.2–1.4%; the example cases are unchanged to within 0.02%. Thanks to Marco Pignone
(@rationalpiper) for reporting it, with the worksheet references (#205).

#### Fixed: ACA premiums in states without the Medicaid expansion

**Owl** treated every state as a Medicaid expansion state, with no premium up to 138% of the poverty
line. In the states without the expansion there is no Medicaid for most adults, and the premium tax
credit only starts at 100% (IRC 36B(c)(1)(A)): income below 100% gets neither and owes the full
benchmark premium. Medicaid now follows the state of residence of each year: 138% in expansion
states, 100% in Wisconsin (which covers adults to 100% under a waiver), and none in AL, FL, GA, KS,
MS, SC, TN, TX and WY (KFF, October 2026). With *Solve ACA brackets with MILP*, the coverage gap is
priced exactly, and so is the applicable-percentage jump at 133%, which only expansion states never
reach: exactly 100% gets the credit and exactly 133% the higher percentage. The self-consistent loop
charges the lowest applicable percentage in the gap rather than the full premium, so that the cost
has no jump to oscillate across, and warns when a year ends there. Thanks to Marco Pignone
(@rationalpiper) for reporting it, with the references and a proposed design (#202).

#### Fixed: PA and MS no longer tax Roth conversions before 59½, and exempt IRA withdrawals from 59½

Pennsylvania treats a trustee-to-trustee Roth conversion as nontaxable at any age and exempts IRA
distributions from 59½ (2025 PA-40 instructions, pp. 12–13). Mississippi leaves conversions out of
gross income (Miss. Code 27-7-15(4)(ff)) and denies its retirement exemption to early distributions
(35 Miss. Code R. 3-02-07-104). **Owl** gated conversions behind the same age as withdrawals (60 in
PA) and exempted MS withdrawals at any age: in the reported case, a \$20,000 conversion at 55 paid
\$614 of PA tax. The state data's `roth_conversion_eligible` flag becomes a three-valued
`roth_conversion` field: `"exemption"` (counts toward the retirement exemption, with its age; the
default), `"taxed"` (MD), or `"excluded"` (PA, MS: left out of state income at any age, apart from
the exemption). PA and MS now exempt withdrawals from 59½. The former flag is still read. Thanks to
Marco Pignone (@rationalpiper) for reporting it, with the PA references and a fix (#203).

#### Fixed: Roth earnings can no longer be withdrawn before 59½ without tax or penalty

A Roth distribution comes from contributions first, then conversions, and earnings last (IRC
408A(d)(4)(B)), and before 59½ its earnings part is taxable and carries the 10% additional tax
(408A(d)(2)(A); Pub. 590-B). **Owl**'s five-year retainer kept only recent conversions in the
account, so once they had matured the earnings could come out early with neither: in the reported
case, \$51,506 converted and \$74,387 withdrawn before 59½. Each person's Roth withdrawals before
59½ are now kept within the starting Roth balance plus the conversions and contributions made
since, which forbids early earnings rather than taxing them. The starting balance counts entirely
as contributions and conversions, and the limit ends at the first passing. Thanks to Marco Pignone
(@rationalpiper) for reporting it, with the legal references and a fix (#209).

#### Fixed: a previous-year MAGI above the year's income ceiling no longer makes optimize mode infeasible

With *Solve Medicare brackets with MILP*, the first two plan years take their IRMAA bracket from the
previous MAGIs entered, but the top bracket was still capped at the year's income ceiling. A
previous MAGI above that cap, such as a one-time gain two years back with modest savings now, left
no feasible plan, reported as a bequest or spending floor set too high, while the loop mode solved
the same case. The known previous MAGI now fits that bracket, and both modes give the same plan.
Thanks to Marco Pignone (@rationalpiper) for reporting it, with a fix (#215).

#### Fixed: MAGI of exactly \$500,000 (\$750,000 joint) is the top IRMAA tier

Every IRMAA tier excludes its upper edge except the top one: "More than \$160,000 but less than
\$500,000" and "At least \$500,000" (42 U.S.C. 1395r(i)(3)(C)(i)(III); 20 CFR 418.1115, "greater than
or equal to \$500,000", \$750,000 joint). **Owl** charged the tier below at exactly that MAGI, \$48.40 a
month too little per enrollee. The top tier now includes its edge in the loop and optimize modes,
in the first two years read from the previous MAGIs, in the check of the loop's fixed point, and in
the assistant's IRMAA report. Thanks to Marco Pignone (@rationalpiper) for reporting it, with the
legal references and a fix (#216).

#### Fixed: a spouse's own delayed credits come out of the spousal benefit instead of adding to it

When someone receives their own retirement benefit with delayed credits and a spousal benefit,
Social Security computes the combined payment without the credits and subtracts the own benefit
with them to get the spousal part (POMS RS 00615.694; 42 U.S.C. 402(k)(3)(A)). **Owl** added the
full spousal excess on top of the delayed own benefit. Example: with a \$3,000 PIA for one spouse and
\$1,000 for the other, who files at 70, the second spouse gets \$1,500 a month, not \$1,740;
delaying past FRA only pays once one's own benefit exceeds half the other's PIA. The claiming-age
search no longer sees value in such a delay. Thanks to Marco Pignone (@rationalpiper) for reporting
it, with the legal references and a fix (#211).

#### Fixed: Part D IRMAA tiers 2 to 4 use the 2026 CMS amounts

The 2026 Part D income-related monthly adjustments are \$14.50, \$37.50, \$60.40, \$83.30 and
\$91.00 (CMS 2026 fact sheet, Nov 14, 2025; SSA POMS HI 01101.020). **Owl** had the first and last
right but \$36.30, \$58.10 and \$79.90 for tiers 2 to 4, \$1.20, \$2.30 and \$3.40 a month too
low per enrollee. Part B amounts were already correct. Examples whose income reaches those tiers pay
slightly more for Medicare. Thanks to Marco Pignone (@rationalpiper) for reporting it (#214).

#### Fixed: four cells of the joint life expectancy table follow the regulation

The Joint and Last Survivor table used for RMDs when the spouse is the sole beneficiary and more
than 10 years younger was copied from Pub. 590-B (2025), which prints four cells differently from
the regulation, 26 CFR 1.401(a)(9)-9(d) as published in T.D. 9930: (90, 76) is 14.7, not 14.8, and
(112, 102), (112, 103) and (112, 107) are 3.3, 3.2 and 3.0, not 3.2, 3.1 and 2.9. The regulation's
table is symmetric in those cells and governs. Every other stored cell already matched. Only
(90, 76) can reach a plan: a 90-year-old with a 76-year-old spouse had an RMD 0.7% too low. Thanks
to Marco Pignone (@rationalpiper) for reporting it (#217).

#### Fixed: a survivor born on the 1st claims at the survivor FRA a month earlier, and from 59 years 11 months

Someone born on the 1st reaches every age in the month before their birthday (20 CFR 404.102), so a
survivor born on the 1st reaches 60 and their survivor FRA one month before their conventional age.
**Owl** resolved the survivor claim age on the conventional ages: *FRA* filed a month after the full
rate was reached, losing one month of survivor benefit (\$3,000 on a \$3,000 benefit), an explicit
age was capped a month late, and 59 years 11 months, when they reach 60, was not accepted. The
claim age now uses those ages in the engine, the log messages, and the survivor claim-age fields,
which span 59 years 11 months to the month the survivor FRA is reached; a stored age outside that
window is moved into it. Everyone else is unchanged.

#### Fixed: born on the 1st, delayed credits stop at age 70 and the survivor reduction counts one month less

Social Security counts a person as reaching an age on the day before the birthday (20 CFR 404.102),
so someone born on the 1st reaches every age in the month before their birth month. **Owl** already
counted their retirement and spousal reductions on that age, but it did not stop there at 70:
delayed credits end with the month before age 70 is attained (42 U.S.C. 402(w)(2)(A); POMS
RS 00615.690), and a claim at a conventional 70 got a 37th credit, 2/3% of the PIA too much for life.
Their survivor reduction, which is counted in months before the survivor FRA (20 CFR 404.410(c)(1)),
used the conventional age instead and charged one month too many: 71.5% instead of 71.84% at a
conventional 60. Thanks to Marco Pignone (@rationalpiper) for reporting it, with the legal
references and a fix (#212).

#### Fixed: the earliest Social Security claiming age in the interface is the month the engine uses

Benefits start in the first month one is 62 throughout (POMS RS 00201.001): the birth month for
those born on the 1st or 2nd, the month after for everyone else. The engine already used those
months, but the claiming-age fields offered one month earlier (61 years 11 months and 62 years), and
the engine quietly raised such an age. The fields now start at 62 years and 62 years 1 month, and a
saved age below the minimum is raised to it.

#### Fixed: IRMAA in the survivor's first two years uses the joint table of the lookback return

Medicare's income-related surcharge (IRMAA) is set from the MAGI of the tax year two years before
the premium year, and from the table of the filing status on that return: the joint ranges apply to
individuals "who are married and filed a joint tax return for the tax year we use" (20 CFR
418.1115(c), 418.1135(a)). **Owl** picked the table from the premium year instead, so after a
death the survivor's first two years paired the couple's joint MAGI with the single thresholds. A
couple files jointly in the year of the first death, so both of those years look back to joint
returns, and the single table now starts in the third year, in both Medicare modes and in the
assistant's IRMAA report. Example: a couple with \$190,000 of MAGI, below the \$218,000 joint edge,
pays no surcharge, but **Owl** charged the survivor single tier 3 for two years, \$4,592 a year too
much. A survivor's request to SSA to use a more recent year after the death (20 CFR 418.1205(a)) is
not modeled. Thanks to Marco Pignone (@rationalpiper) for reporting it, with the legal references
and a fix (#213).

### Version 2026.10.21

#### Fixed: a January 1 birthday gets the 65+ deductions a year earlier

The additional standard deduction for age 65 (IRC 63(f)) and the OBBBA senior deduction
(IRC 151(d)(5)(C)(ii)) require having attained age 65 before the end of the tax year, and the IRS
treats a person as reaching an age on the day before the birthday (2025 Instructions for Form
1040), hence "born before January 2, 1961" for 2025. **Owl** tested the birth year only, so a
person born on January 1 got these deductions a year late: a single filer born January 1, 1962,
had a 2026 deduction of \$16,100 instead of \$24,150. The age test now counts a January 1
birthday in the year before. Thanks to Marco Pignone (@rationalpiper) for reporting it, with the
legal references and a fix (#207).

#### Fixed: Medicare and ACA coverage change in the month of the 65th birthday

Medicare starts in the month of the 65th birthday, or in the month before for a birthday on the 1st
(CMS), and premiums are monthly. **Owl** charged a full year of Part B, Part D, and IRMAA in the year
of that birthday, and no ACA premium for its months before Medicare: someone born in December paid
12 months of Medicare for one month of coverage, \$2,232 of Part B alone at the 2026 premium. The
first Medicare year is now prorated by the months covered, and marketplace coverage runs until
Medicare starts. The premium tax credit is computed by the month (IRC 36B(b)), and a month with
Medicare is not a coverage month (36B(c)(2)(B)): each coverage month pays the lesser of its
benchmark and 1/12 of the expected contribution, and the benchmark follows who is enrolled that
month (26 CFR 1.36B-3(f), Example 7). Under `withACA = "optimize"`, the year a spouse moves to
Medicare is priced on the months-weighted benchmark, which keeps one premium cap per year and
charges slightly more, only for incomes between the two caps (#208).

#### Fixed: the ACA poverty line is the tax household's

For the premium tax credit, family size is the tax household, both spouses on a joint return
(IRC 36B(d)(1), 26 CFR 1.36B-1(d)), whoever is enrolled. **Owl** used the 1-person poverty line once
one spouse was on Medicare, which lowered the 400% cliff for 2027 from \$86,560 to \$63,840: at
\$70,000 of MAGI, a 60-year-old's benchmark of \$9,572 was charged in full instead of \$6,972. The
benchmark still covers only the spouse enrolled. Thanks to Marco Pignone (@rationalpiper) for
reporting it, with the legal references and a fix (#199).

#### Fixed: HSA contributions are prorated in the year Medicare starts

The HSA limit is the sum of monthly limits, and the monthly limit is zero from the first month of
Medicare (IRC 223(b)(2) and (b)(7)). **Owl** dropped the whole contribution in the year of the
65th birthday. It now keeps the share for the months before Medicare, which starts in the
birthday month, or the month before for a birthday on the 1st: 5/12 of the entry for a June 15
birthday, and 11/12 of the year before for a January 1 birthday, which **Owl** used to keep whole.

#### Fixed: the ACA poverty line is the guideline of the year before

The premium tax credit measures income against "the most recently published poverty line as of the
1st day of the regular enrollment period" (IRC 36B(d)(3)(B); 26 CFR 1.36B-1(h)). Open enrollment
starts in November, so coverage in 2026 uses the 2025 guideline (\$21,150 for two people), not the
2026 one (\$21,640). **Owl** used the coverage year's guideline grown by a year of inflation, which
made the 138%, 150% and 400% lines about 2.3% too generous. Years past the last published guideline
now grow it by inflation from its own year, which also corrects a plan starting after that year.
Thanks to Marco Pignone (@rationalpiper) for reporting it, with the legal references (#200).

#### Fixed: ACA uses the 2027 applicable percentage table, and exactly 400% of the poverty line qualifies

Rev. Proc. 2026-26 publishes the 2027 table (2.15% below 133% of the poverty line, up to 10.22%).
**Owl** applied the 2026 table to every year; the tables are now keyed by year, in both the loop and
optimize modes, with the latest carried forward. In loop mode, income of exactly 400% of the poverty
line paid the full benchmark; IRC 36B(c)(1)(A) covers income that "does not exceed 400 percent",
so it now gets the credit, as it already did in optimize mode. Thanks to Marco Pignone
(@rationalpiper) for reporting it (#201).

#### Fixed: the 82.5% survivor limit caps the benefit after the survivor's age reduction

When the deceased spouse had claimed early, **Owl** took the greater of their benefit and 82.5% of
their PIA as the survivor's base and then reduced it for the survivor's age. The law reduces the
full PIA for the survivor's age first and only then caps it at that greater amount: the limit
applies to the benefit "after application of subsection (q)" (Social Security Act 202(e)(2)(D);
POMS RS 00615.320). With a PIA of \$3,000 claimed at 62 and 1 month, a survivor filing at 62 now
gets \$2,389.29 a month instead of \$1,971.16, and the gain from waiting until the survivor FRA
drops from \$504 to \$86 a month. Survivors filing at their survivor FRA, and deceased spouses who
claimed at or after FRA or never claimed, are unchanged. Thanks to Marco Pignone (@rationalpiper)
for reporting it, with the legal references and a fix (#210).

#### Fixed: a surviving spouse's home sale more than 2 years after the death uses the \$250,000 exclusion

**Owl** chose the primary-residence exclusion once per plan, so a couple's home sold by the survivor
kept the \$500,000 exclusion however long after the death. The joint amount carries over only for a
sale "not later than 2 years after the date of death" (IRC 121(b)(4)); after that the limit is
\$250,000 (121(b)(1)). The exclusion is now chosen by the year of the sale, both for the gain and for
the balance sheet's estimated disposition cost. With **Owl**'s dates (death on December 31, sale on
January 1), the survivor keeps \$500,000 for a sale in the two years after the year of the death.
A \$400,000 gain realized later now has \$150,000 taxed. Thanks to Marco Pignone (@rationalpiper)
for reporting it, with the legal references and a fix (#218).

#### Fixed: the Social Security claiming-age search is no longer slow with MOSEK

The claiming-age search (*withSSAges*) solves the plan at every open claiming month on parallel
threads. **Owl** passed each model to MOSEK with one call per row and per bound, tens of thousands
per solve, and those calls ran no faster on several threads than on one: the search took 89 s on
Case_jack+jill with MOSEK against 20 s with HiGHS. The model now goes in with a few bulk calls, and
the same search takes 17 s. The model MOSEK solves is unchanged.

### Version 2026.10.20

#### New: the loop says when Social Security did not settle

Under the default loop, the taxable share of Social Security is a constant in each LP, so a dollar
of income in a year where benefits are being phased in (50% to 85% taxable) is charged the bracket
rate only, while it also makes up to \$0.85 of benefits taxable. On a couple with most benefit years
in that range, the loop stopped at its iteration cap or in a cycle, \$34k-\$49k of bequest short of
the exact plan (#193). When the loop leaves taxable Social Security unsettled (the plan's own income
implies more than the loop's tolerance, \$50 a year by default, of different taxable benefits over
the horizon), the log now says so and points to `withSSTaxability = "optimize"`. A loop can also
settle on a plan short of the exact one with a small residual, which this does not detect.

#### Fixed: local search can move Social Security taxability and the LTCG regime together

The LTCG regime binaries hold each year's ordinary income on one side of the 15% and 20% thresholds,
gains or not. The local search's Social Security step kept them pinned, and no other step frees both
families at once, so it could not move income under a threshold and the taxable share of benefits
with it. On `Case_john+sally.toml` under `breakpointMethod = "local-search"`, the bequest was
\$20,004 where branch-and-bound finds \$31,778: converting more early lets the couple's income drop
under the 15% threshold later, where benefits are taxed in the phase-in rather than at 85%. The
Social Security step now leaves the LTCG binaries free, and local search finds \$31,778, the
branch-and-bound plan. On the 18 examples, Florin measured no example worse, gains of 0.08% or less
on seven others, and 1.5x the total local-search time. Thanks to Florin Mateoc for finding it,
explaining it, and proposing the fix (#197).

#### Fixed: an optimized Social Security claiming age is never worse than one entered by hand

The claiming age was chosen inside the solve, with a binary per claiming month. Each candidate
month's benefits were taxed at the share settled for the current one, so the choice ignored how a
later claim changes the tax on benefits, and it kept the earliest open month. On the case reported
in #195, it chose 66 9/12 for \$212,035/yr where entering 68 6/12 by hand gives \$212,233/yr.
Taxing each candidate exactly inside the solve was tried and dropped: neighbouring months differ by
less than the solver's gap, and a single solve took minutes instead of seconds. **Owl** now solves
the plan once for each open claiming month, with the case's own options, and keeps the best, so
the age chosen is never worse than any age entered. With both spouses selected, each age is
searched in turn with the other held, until neither moves. The reported case now gets 68 5/12 at
\$212,236/yr (40 solves, 1.4 s), or 69 6/12 at \$213,350/yr with all tax thresholds solved exactly.
The claiming-month binaries and their benefit tables are removed from the model. Thanks to
@sengsational for following up with the hand-entered ages that showed it (#195).

#### Changed: scenario runs keep the plan's claiming ages

Historical-range, Monte Carlo, spending-optimization, and regret runs passed *Optimize SS claiming
age for...* on to every scenario, which chose the age again knowing that scenario's returns and
lifespans. A claiming age is decided once, without that knowledge: these runs now hold the ages
the plan has, chosen by a solve under the life expectancies entered, and say so in the log. In the
regret sweep, this leaves the first-year conversion as the only decision that varies. The MCP
historical-range and Monte Carlo tools, which loop over scenarios themselves, hold the ages too,
and their run-time estimate now times one solve at the ages chosen rather than the whole search.

### Version 2026.10.17

#### Fixed: optimized Social Security claiming ages can no longer be in the past

When optimizing claiming ages, Owl let the solver pick any month from 62 to 70, including months
already behind someone who has not yet claimed. The benefit table paid such a past age a full first
year at its reduction factor, as if benefits had been collected retroactively, which SSA does not
do. A 66 9/12-year-old planning to claim at 70 was told to claim at 65 11/12, the latest age whose
first check would have arrived in January. The earliest claiming age offered is now the age reached
in the current month. Thanks to @sengsational for reporting it (#195).

#### Changed: a past claiming age can no longer be selected for optimization, instead of being skipped

An entered claiming age already behind someone means that person is collecting, so Owl left them out
of the optimization even when they were selected, without a word, and wrote back the same age. Such
an individual is now not offered in the *Optimize SS claiming age for...* selector (nor is `both`),
a stale selection naming them is reset to `none`, and `withSSAges` raises an error when it selects
them through the API. If the person is not collecting yet, enter a claiming age from this month on.

#### Fixed: optimizing one spouse's claiming age accounts for the spousal and survivor benefits

When only one spouse's claiming age was optimized, the spousal add-on and the survivor benefit that
depend on it were carried from the previous solve rather than seen by the optimizer. It therefore
missed that claiming later raises the benefit a longer-lived spouse inherits, and could settle on an
earlier age that pays the household less than the age entered. In the case reported in #195, with
the other loops made exact, it chose 66 9/12 for \$186,526/yr where claiming at 70 gives
\$188,445/yr. When one age of a couple is free, Owl now tabulates every benefit the household
receives for each candidate age, so the choice is exact: here it picks 70. When both ages are
optimized, spousal and survivor amounts are still settled by the self-consistent loop. Small
differences between an optimized and a fixed-age solve at the same age can remain in loop mode,
where taxable Social Security and Medicare premiums land on slightly different fixed points.

#### Fixed: the spousal benefit keeps its full first plan year and no longer depends on listing order

The spousal add-on starts the month after the later spouse claims. When that claim predated the
plan, Owl still cut the first plan year as if the add-on began then: a spouse with a PIA of \$800
married to one with \$3,000, both collecting since 2024, was credited \$9,507.50 in 2026 instead of
\$12,255.00. Separately, an age entered below the earliest claiming age (62, or 62 1/12 for most
birthdays) is raised to it, but the spouse listed first had their add-on timed from the other's
age before it was raised, so it started a month early and the result changed when the couple was
listed the other way round. The first year is now cut only when the add-on starts within the plan,
and all ages are raised before any benefit is computed. Thanks to Florin Mateoc for reporting it
and proposing the fix (#198).

#### Fixed: rows being typed in the Debts and Fixed Assets tables no longer vanish

A row added to the *Debts* or *Fixed Assets* table stays in the browser until all its required cells
are filled, and only then reaches Owl. Each time a row was completed, Owl stored the table and fed
the stored copy back to the editor, which Streamlit takes as a new table: it rebuilt the editor and
dropped every row still being typed. Entering several assets before their years, then giving the
first one a year, made the others disappear. The editors now keep the table they started with while
their edits go to the case, so incomplete rows stay on screen until they are finished. A row with an
empty required cell is still left out of the case and of the downloaded workbook until it is
completed. Not specific to the latest Streamlit release. Thanks to Dale Seng for reporting it,
with a screencast (#194).

#### Fixed: the top IRMAA tier is no longer indexed before 2028

Owl indexed every IRMAA threshold to inflation from the first plan year. The Bipartisan Budget Act
of 2018 froze the top tier at \$500,000 single and \$750,000 married filing jointly, with CPI
indexing starting only in 2028, while the lower tiers are indexed every year. Raising the top tier
with inflation in the 2026 and 2027 bill years understated Part B and Part D premiums for households
with MAGI near \$500k/\$750k. The top tier now stays at its nominal value through 2027 and follows
inflation from 2028; the lower tiers are unchanged. The same thresholds are used by the
self-consistent loop, the Medicare MILP, and the assistant's `explain` headroom. Thanks to
@bkbaugh for reporting it, with the statute and the lines of code involved (#191).

### Version 2026.10.15

#### New: the assistant asks before starting a long scenario sweep

A sweep's cost is the number of solves times the time each takes, and both vary widely: 1000
Monte Carlo scenarios with Medicare solved as a MILP is a different undertaking from a few dozen
historical years in loop mode, yet the MCP tools started either without a word. The six sweep tools
(`run_stochastic`, `run_spending_bequest_frontier`, `run_year1_robustness`,
`run_longevity_stochastic`, `run_historical`, `run_monte_carlo`) now time one solve of the plan
before running the scenarios and project the total, crediting the threaded sweeps with their
measured parallel speed-up. A run projected beyond two minutes stops there and returns
`needs_confirmation` with the estimate, the options driving the cost (MILP families, optimized
claiming ages) and cheaper alternatives (the loop, fewer scenarios); the assistant relays them,
asks whether to proceed, and runs it only with `confirm_long_run=true`. The intake interview now
asks how long the user is willing to wait, and an estimate within that budget runs without asking
again. A run beyond an hour is flagged `very_long` and its estimate, given in hours or days, is
always put to the user, whatever budget they stated; nothing is refused once they agree. The two
thresholds are set by the `OWL_MCP_CONFIRM_MINUTES` and `OWL_MCP_VERY_LONG_MINUTES` environment
variables. After the first solve, the assistant quotes its time with a rough cost for each sweep
it offers. On
`Case_jack+jill`, the projection for `run_stochastic` was 12 s against 11.8 s measured. Runs under
the threshold, and every solve outside the MCP tools, are unchanged.

### Version 2026.10.14

#### Fixed: long historical plans no longer end in a solver error with HiGHS

The Roth 5-year rule keeps the last five years of conversions in the Roth account at their
compounded value. It compounded them with every loss year counted as zero growth, while the
account itself grew at its real returns. After a loss, a Roth holding only recent conversions was
then asked to keep more than they were worth, and the one plan that satisfied both was no
conversion at all, found only through two nearly equal sets of coefficients. HiGHS's simplex
stalled on it and Owl reported "solver error"; MOSEK found the plan. Conversions are now compounded
at the account's real returns, losses included, and only the gains of a recent contribution are
retained, none after a loss.

The failures needed loss years in the sequence: constant returns never failed at any horizon,
balance or inflation, and a long plan failed more often only because it spans more of them. On a
one-person case over 65 years of historical returns, 20 failing combinations of balance, horizon
and start year now all solve, as do all 72 historical sequences of `Case_avery+quinn` with every
family in loop mode (8 were solver errors) and the issue #139 case. The rule only relaxes: a plan
that converts before a loss can now do better, and no plan becomes infeasible.

Thanks to Dmitry Fink (@finik) for reporting the failures and for the careful work behind them: the
HiGHS fallback that brought them to light and the exact-arithmetic and MOSEK checks of the stuck
models (#184), the `Not Set` status found on a bootstrapped sequence (#188), and the related change
to which earlier iterate the loop falls back on (#186), each still under review on its own.

#### Fixed: a plan that ends before anyone reaches 65

Such a plan stopped with "negative dimensions are not allowed": the Medicare setup took the year
Medicare starts to lie within the plan, and when it did not, sized its tables with a negative
number of years. Medicare now simply does not start within the plan, and it solves with no
premiums. This comes up when a plan is cut short, for example to find the last year a plan can
still pay for everything on a hard market sequence.

#### Fixed: `owlcli run` saves the workbook when results are in today's dollars

With real-dollar worksheets selected (`worksheet_real_dollars`), `owlcli run` stopped with
"unsupported operand type(s) for +" before saving its results (#190): the name of the real-dollar
file was built by adding "_real" to a path as if it were text. The workbook is now saved as
`<case>_results_real.xlsx`, and the CLI reports that name. The same mistake stopped `readConfig`,
`saveConfig`, `saveHFP` (given no extension) and `saveWorkbookCSV` when called from Python with a
`pathlib.Path`; every file a plan reads or writes can now be named with a path or a string, and
`saveWorkbook` returns the name of the file it saved. Thanks to Scott Snyder (@ssnyder379) for the
report.

#### Maintenance: `astral-sh/setup-uv` 10.3.0 in the test workflow

The GitHub Actions test workflow installs uv with `astral-sh/setup-uv` 10.3.0 instead of 10.2.0
(#189, from Dependabot).

#### Maintenance: Updated dependencies

`streamlit` 1.65.0 → 1.66.0, `anthropic` 1.13.0 → 1.14.0, `async-lru` 2.3.0 → 2.4.0, `fonttools`
4.66.1 → 4.67.0, `jedi` 0.20.0 → 0.20.1, `jsonpointer` 3.2.0 → 3.2.1, `nbconvert` 7.17.1 → 7.17.2,
`numpy` 2.5.3 → 2.5.4 (Python 3.12 and up), `platformdirs` 4.12.4 → 4.13.0, `pyarrow` 25.0.1 →
26.0.0, `pydantic` 2.14.0 → 2.14.1, `pydantic-core` 2.50.0 → 2.50.1, `soupsieve` 3.0 → 3.0.3 (2.10
also locked), `starlette` 1.7.0 → 1.8.0, `truststore` 0.10.4 → 0.10.5; `httptools` is no longer
required.

### Version 2026.10.11

#### New: health care in the MCP, from setting it to explaining it

The tools that take parameters (`run_from_params`, `save_case`, `compare_to_baseline`,
`explain_results`, and the stress tools) accept `other_medical_expenses`,
`medical_inflation_excess`, `include_medicare_part_d`, and `medicare_part_d_base_premium`, which
before could be set only in a case file. HSA balances given without `other_medical_expenses` are
flagged in `assumed_defaults`: the HSA can then pay only Medicare premiums and stays mostly locked.
The intake prompt asks for out-of-pocket medical expenses when there is an HSA and about drug
coverage at Medicare age. `explain_case` and `owlcli explain` report a `health_care` block (Medicare
start years and Part D, ACA benchmark and start year, other medical expenses, medical inflation).
`explain_results` gives what crossing the next IRMAA tier adds to premiums, the ACA MAGI against the
Medicaid line and the 400% FPL subsidy cliff with the premium at stake, and a `health_care` section
with lifetime Medicare premiums (IRMAA part and years), ACA net premiums, out-of-pocket expenses,
and HSA withdrawals. Its caveat now names ACA premiums among the quantities held fixed.

#### Fixed: `explain_results` on a plan that parks income on an IRMAA or ACA threshold

With `withMedicare` or `withACA` set to `"optimize"`, the optimizer can place MAGI exactly on a
threshold, such as the 400% FPL subsidy cliff, and the solver returns it a fraction of a cent
above. The explanation compared it exactly and read such a plan as past the threshold. The IRMAA
tier and the next-tier cost, and the ACA Medicaid line and cliff, now allow a dollar of slack, as
the convergence check does: the bracket formulations start each higher bracket \$2 above its
threshold, so no MAGI lies in between. The ACA net premium for the first year, reported before
this release too, read a quantity that is zero in optimize mode and showed \$0; it now shows the
premium paid in either mode.

#### New: medical prices can grow faster than inflation, with `setMedicalInflation`

Medical prices have long outpaced general inflation, yet every health cost in a plan followed it. The
new optimization parameter `medical_inflation_excess` (percent a year, `0` to `10`, default `0`) and
the method `plan.setMedicalInflation()` let them grow faster. Medicare Part B and D premiums, base and IRMAA
surcharges alike, the ACA benchmark premium, and `other_medical_expenses` then grow each year by
inflation compounded with the excess. Tax brackets, IRMAA thresholds, and the poverty line that sets
ACA subsidies keep following inflation, as the law indexes them. The setting is on the Run Options
page beside the other medical expenses, and the documentation points to FRED for past medical-care
versus all-items CPI. At the default of `0`, plans solve exactly as before. Thanks to Dmitry Fink
(@finik) for contributing it (#182).

### Version 2026.10.10

#### New: branch-and-bound nodes in the Summary, and the solver option `mipMaxNodes`

The Summary has two new rows. *MIP nodes* gives the branch-and-bound nodes of the solve that produced
the accepted plan, then those of the whole solve: every iteration of the self-consistent loop, its
retries and repairs, and, under local search, the loop that seeds the search and every restricted
solve. It reads n/a when the plan was solved as a pure linear program. *MIP node limit* gives the
cap in force. With verbose output, each iteration of the loop logs its node count beside its gap.
MOSEK counts the nodes it solved, as HiGHS does, so the two engines' counts can be compared; the
local search's step log used to count MOSEK's branchings instead.

The expert solver option `mipMaxNodes` sets the cap on every branch-and-bound solve. The engines
cap different things: HiGHS caps nodes (default 1,000,000), MOSEK caps branchings (no cap by
default). The local search's restricted solves keep their own cap, `localSearchStepNodes`. The
option is not in the interface: enter it under the extra solver options, or set it in the case file.

A third row, *Local search step node limit*, gives the cap on each of the local search's restricted
solves: `localSearchStepNodes` when set, otherwise the engine's default (3,000 nodes with HiGHS,
20,000 branchings with MOSEK). It reads n/a when the plan was not solved by local search.

A fourth row, *MIP solves stopped at node limit*, counts the mixed-integer engine runs that stopped
at the node limit, out of all of them, with the local search's restricted solves counted apart:
their cap is small by design, so reaching it is routine there, while a main solve reaching
`mipMaxNodes` means that solve was cut short. Each engine says when it stopped at the limit (MOSEK's
termination code, HiGHS's model status), so the count does not depend on comparing node counts with
a cap that MOSEK sets in branchings. Runs include HiGHS's retries of a MIP it reported infeasible.
The row reads n/a when the plan was solved as a pure linear program; the main count reads `0 of 0`
when the loop that seeds a local search solved only linear programs.

The regret sweep carries the same counts. `run_conversion_regret_sweep` returns `node_limit_hits`,
one row per scenario summed over all its solves, the baseline's and every pinned one's, and
`summarize_conversion_regret` reports the sweep's totals, with the number of windows in which a
main solve stopped at the limit. They count engine runs, not solves: a solve makes one per
iteration of the loop, plus its repairs and local-search steps.

#### Fixed: the MCP tools described big-ticket items with the wrong sign

The MCP tool descriptions, the guided intake prompt, and `info/mcp.md` said big-ticket items were
expenses entered as positive amounts. The amount goes to the plan unchanged, where a positive amount
is money coming in, as in the Household Financial Profile, so an expense entered as told was counted
as income. The amounts are signed: negative for an expense, positive for an inflow (Refs #180).

#### Changed: dependencies updated

httptools 0.9.0, narwhals 2.27.1 and pycparser 3.11. The optional `assistant` extra moves to
anthropic 1.13.0, and the `notebooks` extra to executing 2.3.0, json5 0.17.3 and soupsieve 3.0.

### Version 2026.10.9

#### New: the OBBBA senior bonus can be solved with the plan (`withSeniorBonus`)

The \$6,000 deduction for each individual aged 65 or older (tax years through 2028) shrinks by \$6
per \$100 of MAGI above \$75,000 single or \$150,000 joint. Owl set it from the previous iteration's
MAGI, so a solve could not weigh a conversion against the bonus it costs, and could settle on a
plan that is consistent with itself yet worse: on `Case_dana` with historical returns, holding the
first year's Roth conversion to a smaller amount left up to \$1,283 more than the optimized plan,
in six of the start years tried. The new solver option `withSeniorBonus = "optimize"` makes the
phase-out part of the problem, with one binary per bonus year for the point where the bonus is
gone, three at most. The `breakpointMethod` presets set it, so the Summary's breakpoint method
lists "senior bonus"; local search leaves those binaries free in every step. A state that follows
the federal deduction still takes it from the previous iteration. The default stays `"loop"`.

#### Changed: mixed-integer solves run in hundreds of dollars

Every mixed-integer solve, with HiGHS or MOSEK, now hands the solver its amounts in hundreds of
dollars and converts the answer back; plans and results stay in dollars. A binary choice has no
unit, so the large coefficients that switch a dollar amount on or off shrink a hundredfold while
every other coefficient keeps its size. In dollars, a long plan whose balances reach tens of
millions put coefficients near a billion beside coefficients near one, and HiGHS presolve called
feasible plans infeasible: 196 times over two sweeps of historical start years with
`withdrawalOrder = "taxable_first"`, and none in tens, hundreds or thousands. Plans solved as pure
linear programs are untouched. On the example cases with mixed-integer options, results agree with
the dollar solves within 0.3%, as the self-consistent loop stops at slightly different plans.
Larger units made exact Medicare and local search faster and `withdrawalOrder = "taxable_first"`
slower; over the example cases, hundreds were the fastest overall, with exact Medicare 4.6 times
and local search 1.3 times faster than in dollars, and `taxable_first` 1.6 times slower. The
expert solver option `mipScaleOrder` sets the unit as a power of ten (default 2, hundreds); `0`
solves in dollars, so that every number the solver sees can be checked against other
calculations (#178).

#### Maint: Updating dependencies and increment version

Updates MOSEK, pyparser, pydantic, anthropic, json5, and a few others.

#### New: a loan can be paid off by the sale of the property it finances

A mortgage kept being paid for the rest of its term after the house it financed was sold. The
*Debts* table now has an optional `property` column naming a residence or real estate in *Fixed
Assets*: the loan is then paid off in the year that property is sold, out of the sale proceeds,
and nothing is paid after. Tying the loan to the property rather than to a year keeps the two in
step when the sale year moves, as it does with a `yod` counted back from the end of the plan.
An empty cell keeps the loan running to its term, so existing workbooks give the same plans. A
link that cannot be honored is an error rather than a loan quietly run to term: a property that is
missing, named twice, inactive under an active loan, or sold before the loan starts. In the UI the
column is a dropdown of the residences and real estate in *Fixed Assets*, and a link to a renamed
or deleted property stays visible with a warning. The example workbooks carry the column. Thanks
to Florin Mateoc for the original suggestion (#173).

#### Fixed: `withdrawalOrder = "taxable_first"` could close a gate no plan needs

The gates of the taxable-first order used one big-M for every row: the whole portfolio
compounded at the best return any account sees, each year. With accounts invested differently
over a long plan it reached hundreds of times the real portfolio (\$973M against \$13M in one
case), beyond what HiGHS resolves reliably. HiGHS then called feasible plans infeasible in
presolve, or closed the last year's gate though nothing used it, forcing the taxable account to
end at zero. The taxable money then had no value to the objective, and the solver could spend
it on taxes: one plan sold its whole taxable account in the first year and bought most of it
back, paying \$500k of tax, for a bequest of \$3.5M instead of \$5.5M. Each gate row now has its
own bound, the best growth path through the one-way order of the accounts (tax-deferred to Roth
to taxable), 15 times tighter in that case. Over that case's first 40 Monte Carlo paths, presolve
no longer calls any plan infeasible (24 times before) and no plan sells and buys back its
taxable account. Long plans in strong markets still reach balances, and so bounds, of hundreds
of millions of dollars, where HiGHS presolve can still misjudge a plan, though less often.
Reported by @ravishahani (#178).

#### Fixed: a rate below 1% in Debts or Fixed Assets read as 50 times more after a reload

Reading a workbook multiplied every `rate` and `commission` between 0 and 1 by 100 in the *Debts*
and *Fixed Assets* sheets, taking it for a fraction such as 0.045 for 4.5%. These columns hold
percent numbers, and small ones are expected: 0.5% of real growth for a residence became 50%, a
0.9% loan 90%. A plan saved and opened again, in the UI, the CLI or through `save_case`, changed.
Values are now read as typed. Only a cell the spreadsheet formats as a percentage (4.50%, which
stores 0.045) is converted. The example workbooks hold whole percents and read as before. Thanks
to Florin Mateoc for reporting the bug and proposing the fix (#176).

#### Fixed: a solver option with a value Owl does not know is refused

`withMedicare`, `withACA`, `withLTCG`, `withNIIT`, `withSSTaxability` and `withdrawalOrder`
select a mode by name, and a value Owl did not know solved as something else without a word.
`--solver-opt withSSTaxability=0.85` arrived as the text "0.85" and ran the loop instead of
pinning the fraction; "optimise" or "Loop" ran the loop; `withMedicare` "true" dropped Medicare
premiums from the plan. Names are now read in any case, numeric text pins the Social Security
fraction (in [0, 1]), `true`/`false` from older case files still read as `"loop"`/`"none"`, and
any other value is refused with the valid choices named. Thanks to Florin Mateoc for reporting the
bug (#174).

#### Changed: the MCP tools take beneficiary fractions and report the solve time

The tools that build a plan from parameters (`run_from_params`, `save_case`, `compare_to_baseline`,
`explain_results` and the stress tests) take `beneficiary_fractions`, `spousal_deposit_fraction`
and `partial_bequest_weight`. Without the first, a couple's partial bequest could only be modeled
from a case file: with every fraction at 1 nothing passes to other heirs at the first death.
Results report `solve_time_seconds` (wall clock and CPU), as the Summary's *Solve time* row does,
and `run_historical`, `run_monte_carlo` and `explain_results` now return the `engine` entry like
the other tools. With local search or branch-and-bound, the explanation tools' note said the
breakpoints were downgraded "from 'optimize'"; it now says only that they were downgraded to the
loop. The MCP documentation lists the parameters added since September (`state_move`,
`breakpoint_method`, `qcds`, a debt's `property`), gives `residualTol`'s default as 50, and the
modeling-capabilities table gives the current default for `partialBequestWeight`.

The stress-test tools (`run_stochastic`, `run_spending_bequest_frontier`,
`run_longevity_stochastic`, `run_historical`, `run_monte_carlo`) now solve their scenarios with
the loop whatever `breakpoint_method` asks, and say so in `breakpoint_method_note`: local search
takes seconds to minutes per solve, which is worth it for the one plan the user acts on, not for
hundreds of scenarios. `run_year1_robustness` already did. The tool descriptions recommend
`breakpoint_method = "local-search"` with `run_from_params` for that one plan.

### Version 2026.10.8

#### Documentation: what to add back for a start date after January 1

With a start date after January 1, the first year counts again the spending already done. The
documentation now says how to offset it: add to the balances the spending and taxes paid since
January 1 minus the wages, benefits and pensions received since then. Wages and benefits stay at
their full-year amounts, so the income received so far is counted again as well, and adding the
gross spending would overstate the balance by that income. Thanks to Florin Mateoc for the
suggestion (#167).

#### Fixed: *Delete case* closes its confirmation after deleting

On the *Create Case* page, the *Delete case* popover stayed open after *Confirm delete*, so a
second click deleted the next case as well. The popover now closes once the case is deleted.

#### Fixed: the UI dropped `partialBequestWeight` from a case file

A case that set the solver option `partialBequestWeight` lost it when loaded in the UI: the
UI solved it with the default weight and saved it back without the setting. The option now
passes through like the other solver options.

#### Fixed: a loop that stopped early could return its first, undercharged iterate

When the loop reached its iteration limit or stalled, it returned the best iterate so far,
including the first one unless Medicare was in loop mode. The first iterate is built from
initial guesses: among others, ordinary income of zero, so every capital gain fits in the 0%
bracket. Its objective therefore looks best and was chosen. With Medicare exact, one example
returned a plan charging no capital-gains tax on \$20,000 to \$28,000 of gains a year, its spending
0.8% too high. The first iterate is now chosen only when nothing else solved.

#### Fixed: exact IRMAA and ACA could charge a bracket the MAGI does not reach

With `withMedicare` or `withACA` set to `"optimize"`, including local search, a MAGI sitting
exactly on a threshold could be charged the higher bracket: the formulation admitted the
threshold in both. Where the money was worth almost nothing to the objective the solver had no
reason to choose the cheaper one, and one example was charged \$622 of IRMAA its MAGI did not owe,
another \$21,812. Each higher bracket now starts \$2 above its threshold.

#### New: `Case_avery+quinn`, a partial bequest that floats

A married couple whose first spouse leaves every account to the children rather than to the
survivor, with the final bequest maximized. The money left at the first death counts toward the
objective only through `partialBequestWeight`, so plans with nearly the same final bequest can
leave very different amounts to the children. At the default weight, below the case's 0.3% gap,
the optimizer could spend that money on taxes the household does not owe. The case sets the
weight to 0.5%, just above its gap, which makes it a test of that edge. It also covers an RMD starting in the first
plan year, QCDs that stop mid-plan, an annuity bought before the plan, and Social Security
taxability through the survivor's years.

#### Changed: the partial-bequest weight defaults to max(1%, twice the gap)

The weight introduced in 2026.10.7, 0.1% of a dollar, was smaller than the 0.3% gap Owl applies
when Medicare is solved exactly. A plan within the gap counts as optimal, so the money left to
non-spouse heirs at the first death was invisible to the solver, which could spend it on taxes
the household did not owe: \$586,494 in one example with Medicare exact, \$68,038 with local
search. The default is now twice the gap, and at least 1%. In that example it removes the
overpayment; the two examples with fractions of 28% give up no final bequest.

#### Fixed: local search could return the loop's inconsistent plan on a tie

Local search keeps the self-consistent loop's plan unless it finds a better one. When the loop
ended on a cycle, the search could find a plan worth exactly as much whose income implies the
costs it is charged, and the loop's plan was still returned. In one example, it charged \$29,703
more taxable Social Security than its income implied, for the same spending. On a tie, the plan
with the smaller fixed-point residual is now kept. Reported by Florin Mateoc (#171).

#### Changed: local search does not repeat its last iteration

The loop stops when two iterations agree, so its last iteration usually rebuilds the problem it
has just solved, and the search repeated itself step for step: 26 of 99 seconds on one example.
When the problem is unchanged, the previous iteration's plan is now returned directly. Results
are unchanged. Reported by Florin Mateoc (#171).

Branch-and-bound still uses the case's gap, 0.3% by default when Medicare is solved exactly, so
there the 0.1% weight on the partial bequest introduced in 2026.10.7 may not count.

### Version 2026.10.7

#### Fixed: exact NIIT could charge far more than the law allows, emptying the partial bequest

With `withNIIT = "optimize"`, including local search, the tax was bounded only from below and
relied on being minimized. Where the plan's money was worth nothing to the objective, typically
a first spouse's assets left to non-spouse heirs while only the final bequest counts, the
optimizer could pay it out as NIIT instead. One couple's plan charged \$190,000 to \$290,000 of
NIIT a year on under \$3,000 of investment income and left a partial bequest of \$98,000; with the
tax capped, the same plan leaves \$2.2M for an identical final bequest. NIIT is now capped at 3.8%
of net investment income.

#### Changed: money left at the first death to non-spouse heirs counts a little

When beneficiary fractions are below 1, part of the first spouse's accounts goes to other heirs.
Neither objective counted it, so wherever the household did not need that money, any amount of it
was equally optimal and the partial bequest was arbitrary. The objective now counts each dollar
left to those heirs as 0.1% of a dollar of spending or final bequest. In the cases measured this
gives up no final bequest and leaves cases with fractions of 28% unchanged; it only breaks the tie.
The weight can be set with the solver option `partialBequestWeight`. Local search now solves its
small restricted problems to a 0.01% gap whatever the case's gap: at the 0.3% gap applied when
Medicare is solved exactly, they stopped before the weight counted, and one couple's plan left
\$1.08M to the first spouse's heirs instead of \$2.20M, with a final bequest \$3,250 lower.

#### Fixed: Graphs lost its images after a visit to Reports

After the fix in 2026.10.6 that stopped a visit to Reports from forcing Graphs to solve the case
again, coming back to Graphs showed no images: Reports refreshed the plan's Financial Profile
tables, which marked the plan itself as changed, and a plan marked changed draws nothing. The plan
now stays solved when the tables are the same; an edit still marks it changed.

#### New: solve time in the Summary

The Summary has a *Solve time* row: how long the last solve took on the clock, with the CPU time
it used in parentheses. Solve times now range from under a second with the default iteration to
minutes with branch-and-bound, so compared cases show what each one cost. The clock time depends
on the machine and on what else it is doing; the CPU time much less so, though with MOSEK on
several cores it can exceed the clock time.

#### Fixed: Spending Optimization with lifespan sampling left out debts and fixed assets

With lifespan sampling on, Spending Optimization solves a copy of the case for each sampled
lifespan. In the app, those copies were rebuilt without the case's debts and fixed assets, so
their payments and sale proceeds were missing from every sampled plan. The copies now carry the
household tables as they stand, including edits made in the Financial Profile. The log also no
longer reports the Debts and Fixed Assets tables as missing each time the app syncs the Financial
Profile.

#### Fixed: phantom ACA and IRMAA inconsistencies with the capital-gains brackets solved as MILP

With `withLTCG = "optimize"` and `withNIIT = "optimize"` (including local search), the split of a
year's capital gains across the 0%, 15% and 20% brackets was allowed to hold a dollar more than the
gains. The solver took that dollar whenever it cost nothing, with gains in the 0% bracket, and the
reported MAGI then read a dollar high. A plan priced at exactly 400% of the poverty line, or at an
IRMAA tier, was reported a dollar above it, and its fixed-point residual showed thousands of
dollars of ACA or IRMAA inconsistency the plan did not have. The split now holds exactly the
year's gains. The exact NIIT also uses the plan's own interest and dividend income rather than the
previous iteration's, so NIIT no longer depends on the iteration. Plans with these options can
change slightly; in the cases checked, the ACA, IRMAA and NIIT residuals are now zero.

### Version 2026.10.6

#### New: local search for the tax breakpoints (expert)

The tax breakpoints (Social Security taxability, Medicare, ACA, capital gains and NIIT) can now be
solved by local search instead of branch-and-bound. Turn on *Solve tax breakpoints by local search
(expert)* in Run Options' advanced options, or set `breakpointMethod = "local-search"` in
`[solver_options]`. Each solve starts from the plan the usual iteration finds, then improves it
through small restricted problems around it, never solving the full problem: it is never worse
than that plan, usually somewhat better, and takes seconds to a few minutes; it is not a proven
optimum. Each restricted problem is limited by solver nodes rather than seconds, so the same case
gives the same answer on any machine. It replaces a fixed Social Security taxable fraction with
the IRS formula, and the log says so. `mipStrategy` chooses the strategy for breakpoints set to
MILP individually. The Summary has a new *Breakpoint method* row, so that compared cases show how
each treated the breakpoints; the AI assistant tools take `breakpoint_method` and report the
method used. The documentation now calls the full search branch-and-bound rather
than exact: it stops at the solver gap, and the iteration still runs around it.

#### New: one change of state during the plan

A plan can now move once to another state. On the *Create Case* page, turn on *Move to another
state during the plan* and enter the year of the move and the new state; in a case file, add
`moves = [ { year = 2031, state = "FL" } ]` to `[basic_info]`. The state of residence on
December 31 taxes the whole year, so the year of the move is taxed by the new state. Leaving the
new state blank stops state taxes from that year. The optimizer plans around the move: leaving a
high-tax state for one without an income tax tends to push Roth conversions past it, and the
reverse brings them forward. Only one move is modeled, and local taxes are not. The AI assistant
tools take it as `state_move`. Thanks to Florin Mateoc (@fmateoc) for proposing it (#159).

#### Fixed: visiting Reports no longer makes Graphs solve the case again

Opening the Reports page marked an unchanged case as modified, so going back to Graphs or
Worksheets solved it again, which can take a minute with the slower options. A case is now
solved again only when something in it has changed.

#### Fixed: survivor benefit when a spouse dies before claiming Social Security

A spouse who died before claiming left the survivor only 82.5% of their PIA. That limit applies
only when the deceased had claimed early and taken a reduced benefit. The survivor now receives
the full PIA, plus the delayed retirement credits earned up to death when death came after full
retirement age: up to 132% of PIA instead of 82.5%. This matters when a spouse plans to claim
late but dies first. Thanks to Florin Mateoc (@fmateoc) for reporting it and supplying the fix
(#169).

#### Fixed: optimized claiming ages are taxed on their own benefits

With `withSSAges = "optimize"`, the tax on Social Security, the IRMAA and ACA incomes, and the
state Social Security exclusion were computed from the benefits of the claiming age chosen in the
previous iteration rather than the age being considered. The result could depend on the starting
ages and report a plan whose taxes belonged to another age. Each candidate age is now taxed on its
own benefits, and the result matches a solve with that age fixed. Thanks to Florin Mateoc
(@fmateoc) for reporting it and supplying the fix (#168).

#### Fixed: exact NIIT mode no longer excludes plans just above the threshold

With `withNIIT = "optimize"`, a year whose income exceeded the NIIT threshold by less than its
investment income (\$250k married, \$200k single) could not be represented, so the optimizer never
considered plans with such a year, and a plan forced into it could be reported infeasible. Each
year now pays 3.8% of the smaller of the excess and the investment income over every income
range, as the statute sets it.

#### Fixed: case files and state data are read and written as UTF-8 on Windows

On Windows, case files were saved in the system's encoding instead of UTF-8, so a case whose
description held characters such as em dashes might not open on another computer, and the state
tax data was read the same way. All text files are now read and written as UTF-8 on every
platform, as the TOML format requires, and a test keeps it that way.

### Version 2026.10.5

#### Fixed: ACA premiums from 138% to 150% of the poverty line

For 2026, the expected contribution between 133% and 150% of the poverty line now rises from 3.14%
to 4.19% of income, as Rev. Proc. 2025-25 sets it, instead of from 2.10%. Households in this range
(above the 138% Medicaid limit) were charged up to about \$160 a year too little for coverage.
Thanks to Florin Mateoc (@fmateoc) for reporting it and supplying the fix (#164).

#### Fixed: ACA *optimize* mode no longer reports feasible plans as infeasible

With `withACA = "optimize"`, an income below 400% of the poverty line whose expected
contribution exceeded the benchmark (SLCSP) premium was treated as impossible instead of paying
the full premium, so a household that could not move its income out of that range was reported
infeasible. It now pays the full premium, as in loop mode. Thanks to Florin Mateoc (@fmateoc) for
reporting it and supplying the fix (#161).

#### Changed: ACA costs nothing up to 138% of the poverty line, and optimize mode follows the sliding scale

Up to 138% of the poverty line, a household is now assumed covered by Medicaid, at no premium, in
both ACA modes; loop mode used to charge the full benchmark premium there and optimize mode 2.10%
of income. This is the rule in Medicaid expansion states; the others are not modeled. In
`withACA = "optimize"`, the expected contribution now rises across each income band as the
statute sets it, as in loop mode, instead of charging each band's top rate, so the two modes
agree. Plans that can keep income at or below 138% now take advantage of it; the *morgan* example
spends about \$2,100 a year more. Thanks to Florin Mateoc (@fmateoc) for reporting it (#165).

#### Fixed: capital gains on taxable accounts with a known cost basis

When a cost basis is entered, the dividends and interest taxed each year and left in the account
now add to it, so they are no longer taxed a second time when sold. The account's unrealized
gain is also placed in its stocks, since bond and cash returns are taxed as they are earned, so
a withdrawal realizes the account's full embedded gain rather than only the stock share of it.
The two corrections pull in opposite directions; in the examples with a cost basis, spending
changes by less than 0.7%. Plans without a cost basis are unchanged. Thanks to Florin Mateoc
(@fmateoc) for reporting it and supplying the fix (#166).

### Version 2026.10.4

#### Fixed: reported taxes and bequests in years where extra cash has no value

When a plan had years whose extra cash could not raise the objective, for example a late surplus
under *maximize spending*, or surplus deposited to a spouse whose accounts pass to other heirs
under *maximize bequest*, taxes could be reported as if all income fell in the top bracket. The
spending objective was right, but the reported taxes, bequests and *Taxes* sheet were not, and
the solve could end without settling. Brackets are now filled from the bottom, and a warning
flags any plan whose brackets still end up out of order. Thanks to Florin Mateoc (@fmateoc) for
reporting it and supplying the fix (#162).

### Version 2026.10.3

#### Fixed: state amounts fixed in statute no longer grow with inflation

Owl inflated every state's brackets, deduction and exemption caps each year. Each state now says
which of these it indexes (`brackets_indexed`, `deduction_indexed`, `exemptions_indexed` in the
state data), so amounts fixed in statute stay nominal, for example New York's brackets, deduction
and \$20,000 pension exclusion, and New Jersey's brackets. Among the retirement exclusions, only
Maryland's is indexed. Plans in these states now show higher state tax in later years. Thanks to
Florin Mateoc (@fmateoc) for reporting it and supplying the fix (#157).

#### Fixed: Maryland and New Mexico retirement exemptions

Maryland's pension exclusion is now \$41,200, its 2025 maximum (it was \$34,300). New Mexico's
65+ exemption is limited to low incomes, so it is now modeled as 0 instead of \$10,000.

#### Fixed: state personal exemptions and credits

New Jersey's \$1,000 exemption per filer and its additional \$1,000 at age 65 are now applied, as are
Maryland's \$3,200 exemption and \$1,000 at 65, and Ohio's \$1,900 exemption. The personal credits of
Arkansas, California, Delaware, Iowa, Nebraska and Oregon now reduce state tax, as does
California's \$153 senior credit at 65. These come from new optional per-filer fields in the state
data (`personal_exemption`, `senior_exemption`, `personal_credit`, `senior_credit`), each saying
whether it is indexed; income-based phase-outs are not modeled.
Thanks to Florin Mateoc (@fmateoc) for pointing out the New Jersey exemption (#157).

#### New: the About page shows the git commit

The version on the *About Owl* page is followed by the git commit when Owl runs from a checkout.

### Version 2026.10.1

#### Fixed: *Download HFP workbook* saves the edits made on the page

Edits to the *Financial Profile* tables, such as ticking *Roth conv fixed*, were left out of the
downloaded workbook until the case had been run. The download now always reflects the tables as
shown.

#### Changed: *Spending vs Bequest* progress counts every scenario

The progress bar advances per scenario instead of per bequest level, and the note on the largest
reachable bequest is reworded.

#### Changed: dependencies updated

charset-normalizer 3.5.2 and cryptography 50.0.2. The optional `assistant` extra moves to
anthropic 1.11.0, and the development tools to pyflakes 4.0.1.

### Version 2026.9.30

#### Fixed: NJ income above \$1M is taxed at the top rate

In New Jersey, a Single filer, or the surviving spouse of a couple after the first death, paid no
NJ tax on taxable income above \$1,000,000. That income is now taxed at the 10.75% top rate, so
such plans show higher NJ tax and lower spending or bequest. No other state was affected. Thanks
to Florin Mateoc (@fmateoc) for reporting it and supplying the fix (#149).

#### Fixed: a married case can omit `pension_indexed` and `pension_ages`

A couple's case without these keys in `[fixed_income]` failed every solve with an `IndexError`.
They now default for each person (indexed, age 65), and a list of the wrong length is reported as
a clear error. Thanks to Florin Mateoc (@fmateoc) for reporting it and supplying the fix (#155).

#### Fixed: the UI's *Stop Roth conversions mid-plan* and *Include Part D premiums* take effect

In the web UI, the year set to stop Roth conversions was ignored, so conversions continued past
it, and turning Part D premiums off still charged them. Both settings now apply to the run and are
kept in the case file saved from it. Passing `includeMedicarePartD` or `medicarePartDBasePremium`
to `solve()` also works now; before, they were honored only on the first solve of a case loaded
from a file. Thanks to @SamMadDev for reporting it and supplying the fix (#156).

#### Changed: faster solves and Monte Carlo runs

Each iteration of the self-consistent loop builds its LP faster. Stochastic runs with historical
Gaussian or lognormal rates fit the rate distribution once per historical window instead of once
per scenario. Thanks to Ben Mabey (@bmabey) for this work (#150, #151, #152).

#### New: timing benchmarks

`uv run pytest benchmarks --benchmark-only` times the LP build, single solves and a Monte Carlo
run, and can compare against a saved baseline; see *Benchmarks* in `CONTRIBUTING.md`. Contributed
by Ben Mabey (@bmabey) (#150).

#### New: plan explanations cover state income tax

In a state with an income tax, `explain_results` reports this year's state tax and the state
bracket reached, with the room left in it (`this_year.state_tax`), and the same for every year
of the plan (`state_tax_brackets`). Plans in states without an income tax are unchanged.

#### Changed: MCP results record the engine and each plan's convergence

`run_stochastic`, `run_year1_robustness`, `run_longevity_stochastic`,
`run_spending_bequest_frontier`, `compare_cases` and `compare_to_baseline` now return the `engine`
entry (Owl version and git commit), like the other results, and so does every response for a plan
that did not solve. `compare_cases` and `compare_to_baseline` also report how each plan's
self-consistent loop ended and its fixed-point residual, so a difference between two plans can be
checked against whether both converged.

#### New: the summary names the Owl version

The plan summary, and the *Summary* sheet of saved workbooks, end with the Owl version and git
commit that produced them.

#### Changed: dependencies updated

MOSEK 11.2.5, fonttools 4.66.1, PyJWT 2.15.1 and sse-starlette 3.5.0. The optional `assistant`
and `notebooks` extras move to anthropic 1.9.0, ipykernel 7.4.0, platformdirs 4.12.2 and
fqdn 1.6.0.

### Version 2026.9.29

#### Fixed: state tax no longer also deducts the federal standard deduction

State taxable income now starts from gross ordinary income, so only the state's own deduction
and exemptions apply. State tax was previously understated in every income-tax state; plans in
those states now show higher state tax and lower spending or bequest. Thanks to Florin Mateoc
(@fmateoc) for reporting it (#147), and to @SamMadDev for reporting it independently (#154).

#### Changed: states that use the federal standard deduction now follow it

AZ, CO, DC, IA, ID, MO, MT, ND and NM take the federal standard deduction each year, including
the additional amount for age 65+, instead of a fixed amount. CO, ID and ND also take the OBBBA
senior deduction. In the state data, `standard_deduction = "federal"` selects this and
`senior_deduction` controls the senior bonus.

#### Fixed: with `withSSTaxability = "optimize"`, state SS exclusion matches the federal amount

States that exempt Social Security now remove exactly the taxable benefit the optimizer
computed, rather than the previous iteration's estimate.

#### New: LTCG family in `plan.fixedPointResidual`

The fixed-point residual now reports the difference between the capital-gains tax charged and
the tax the plan's own income implies, and the self-consistent loop no longer declares
convergence while that difference exceeds `residualTol`.

#### Changed: UI log lines no longer carry the `ScriptRunner.scriptThread` tag

#### New: results record the engine that produced them

`plan_to_dict()` and the results of `run_conversion_regret_sweep()`, `run_stochastic_spending()`
and `run_spending_bequest_frontier()` carry an `engine` entry with the Owl version and the git
commit (suffixed `-dirty` for uncommitted changes, `None` outside a checkout); their summaries
carry the engine of the result they summarize. The solve log line now shows the commit as well.

### Version 2026.9.27

#### Removed: `withDecomposition`, which never worked

The only mode it offered, `sequential`, rounded all five bracket-selector families at once from a
single LP relaxation. That assignment is jointly infeasible even when each family is feasible
alone, so the fixed-bracket solve failed every time and fell back to the monolithic MIP it was
meant to avoid: 16 attempts over four historical windows, 16 failures, no successes. Measured
across eight windows it returned the monolithic answer to the cent every time, having spent one
discarded LP relaxation per self-consistent iteration to do so.

The option is retired rather than rejected, so existing case files load with a warning. The expert
radio is gone from *Run Options*, and the `withDecomposition` key has been dropped from the shipped
examples.

#### Changed: big-M constants are derived per year instead of tuned

Every bracket-selector row is now relaxed by a bound computed from the quantity that row gates —
the year's income ceiling, or the share of a benefit the row switches on — replacing a single flat
constant that had been sized for constraints removed some time ago. On a shipped case over the
historical record the exact all-four MIP went from solving a handful of windows to solving all 72,
71 of them proven optimal, at a median of 236 s. The `bigMamo`, `bigMaca`, `bigMss`, `bigMltcg` and
`bigMniit` options are retired: there is no longer a constant to tune.

#### Changed: the default `epsilon` is 5e-7, which makes the loop converge

`epsilon` puts a small penalty on Roth conversions to break ties. At its old default of `1e-8` it
broke them only nominally, and the conversion schedule stayed free to migrate between
near-equivalent years. Since a conversion moves provisional income directly, each move can flip a
Social Security tier or a Medicare bracket, so the self-consistent loop ended up chasing its own
schedule: `Case_chris+pat` converts in 5 years, but 16 different years see its schedule move
during the search.

Three shipped cases never converged at all and now do -- chris+pat, helen+ruth and
kim+sam-spending, each of which used to exhaust its iteration budget. chris+pat's residual falls
from 2,882 to 48 \$/yr and its iterations from 30 to 20; across the shipped cases the total drops
from 222 iterations to 171. Nine of the seventeen are unaffected at any value.

It also removes three places where HiGHS and MOSEK disagreed, which turn out to have been
degeneracy rather than anything about the solvers: jack+jill's spending (they now agree at
89,532), john+sally's bequest, and dana's 1966 maxBequest window, where the two had differed by
3%.

The cost is real and worth stating: about 0.1 to 0.25% of objective on the four cases that move.
Larger values cost more than they are worth -- at `1e-3` the measured Roth conversion regret falls
23%, the conditioning eating the very quantity being measured, and at `1e-2` conversion years are
deleted outright. `2e-7` fixes nothing, so the useful threshold lies between that and `5e-7`.

#### Fixed: a tight case is no longer reported as infeasible when a plan exists

The self-consistent loop feeds costs back into the next LP, and the first update is a jump from
no Medicare or ACA cost at all to the full amount. On a tight case that one step can put the next
LP outside the feasible region, and the loop stopped there and said no plan satisfies the
constraints. `Case_cameron` -- the smallest household in the examples, at \$119k -- did exactly
that when asked for the most bequest at its own maximum spending, while the same case solved
under `maxSpending` and returned the very plan the loop had just called impossible.

A step that fails is now retried with a shorter one before the loop gives up. Cameron's frontier
is recovered exactly: at 99% of maximum spending the bequest is \$31,748 against a straight-line
frontier value of \$31,748, and at 100% it is \$20,000 against the \$20,000 `maxSpending`
reports independently.

Retrying only on failure is deliberate. Damping every step by a fixed weight also rescues cameron,
but the outcome is chaotic in the weight -- 0.4 and 0.7 break a case that 0.3, 0.5, 0.6 and 0.8 all
solve -- so a weight only changes which cases fall into the hole, and it costs every healthy case
iterations it does not need (3 to 8, or to 17 at heavier damping) while biasing the result, since
the cost estimate is still climbing when the loop exits.

#### Changed: `residualTol` is a per-year bar, defaulting to \$50

The convergence residual sums a family's disagreement over the whole horizon, so comparing it
against a flat figure was three times stricter on a 33-year plan than on an 11-year one. It is now
compared per year. Calibrated over the seventeen shipped cases: anything from \$25 to \$200 a year
produces the same outcome on all of them, so the default sits in the middle of a flat region
rather than on an edge.

The previous \$100 total worked out to about \$3 a year on a typical plan, which nine of the
seventeen could not meet; the loop kept iterating on cases that had nothing left to gain, and the
extra work changed the answer on exactly one of them.

#### New: `plan.fixedPointResidual`

Every solved plan reports how far it sits from the model its own income implies, per tax family.
The self-consistent loop exits on the objective, not on the quantities it feeds back, so a plan
could be called converged while its own income would still move them. `residualTol` now also makes
the loop wait for those quantities to settle before declaring convergence.

#### Note: use MOSEK for the `optimize` tax modes

With every tax mode in `loop` mode the problem is a linear program and both solvers are equivalent.
Once any bracket option is set to `optimize` they are not: over five historical windows of a
shipped case, HiGHS took 49 to 238 times longer than MOSEK and proved optimality in none of them,
returning answers up to \$7,505 below the proven optimum.

#### Changed: fixed assets are those present in January

The *Fixed Assets* table lists what is owned at the beginning of each year, and the documentation
now says so as a rule: an asset appears in the first year it is present in January. One already
owned carries the current year; one bought during 2026 is entered as 2027; one sold during its
`yod` was there that January, so it stays listed that year and its proceeds reach savings the
following January. Entered that way a purchase paid for with a big-ticket item neither
double-counts on the balance sheet in the year it is bought, nor loses a year of appreciation.
No change in behaviour.

#### Changed: *Spending vs Bequest* notes are bulleted, with wrapped lines indented under their text.

#### Changed: *Stress Tests* Improve wording for reporting computing time in UI.

### Version 2026.9.21

#### Fixed: state retirement-income exemptions ([#145](https://github.com/mdlacasse/Owl/issues/145), [#146](https://github.com/mdlacasse/Owl/issues/146))

The state retirement-income exemption is now applied per person. Each spouse is limited by
their own age and by their own eligible income, and an unused portion cannot be claimed by
the other spouse. Couples in states such as NY and CO were previously limited to a single
exemption. Roth conversion income now counts toward the exemption, as do pensions, so
conversions are no longer taxed by states that exempt them (e.g. IL, PA, NY). A new
`roth_conversion_eligible` field in the state tax data marks where conversion income
qualifies; it is `false` for MD, whose pension exclusion does not cover IRAs.
The NY exclusion now starts at age 59½, and KY's \$31,110 exclusion now covers IRA
distributions and conversions, not only pensions.

#### Fixed: state income tax brackets and deductions updated to 2026

The state tax table was audited against the Tax Foundation's 2026 compilation and the laws
enacted in the 2026 sessions. Brackets or deductions were corrected in 24 states: AL, CA, GA,
HI, ID, IL, KS, KY, LA, MA, ME, MI, MO, MS, MT, NE, NM, OK, RI, UT, VA, VT, WI, and WV. Notable
changes include GA's 4.99% rate, UT's 4.45% rate, KS's two-rate structure, ME's new 2% surtax
above \$1M, and CA's 1% surtax, which now starts at \$1M for couples as well. The standard
deduction field now also includes each state's personal exemptions. Most corrections lower
state tax by \$50 to \$1,300 a year at typical retiree incomes; results for cases in these
states will change.

### Version 2026.9.16

#### Fixed: case files from `save_case` load in the web UI ([#144](https://github.com/mdlacasse/Owl/issues/144))

A couple's case saved by `save_case` failed to load on the *Create Case* page. The `spouses`
allocation type is now an input shorthand only: its single pair is expanded to the equivalent
`individual` allocation, so existing case files still load and results are unchanged.

### Version 2026.9.2

#### Changed: the fixed-asset bequest note says when the figure is path-dependent

Whether an asset's today's-dollar bequest value moves with the drawn inflation path is a
property of the asset table, not of the rates: a real-rate asset quoted at the plan's start
cancels the deflator exactly, while a nominal one never does.
`fixedassets.bequest_value_is_inflation_path_dependent()` reports it, and the stochastic
results carry it as `fixed_assets_path_dependent`, so the caveat appears only where it applies.


#### Changed: Consistent use of first-year spending vs spending basis

In graphs and in the UI, the use of first-year spending is made consistent. While it
only differs when a *smile* profile is chosen, reporting both and distinguishing
between them avoids unnecessary confusion.

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

#### Maintenance: Updated dependencies (again) to silence GitHub's dependabot.
Upgrade to Streamlit 1.62.

### Version 2026.8.18

#### Maintenance: Updated dependencies to silence GitHub's dependabot.

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
