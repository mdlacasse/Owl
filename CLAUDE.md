# CLAUDE.md — fork `fmateoc/Owl` (not part of upstream)

This fork extends Owl (upstream `mdlacasse/Owl`) so that one NY-metro couple can decide when to retire, when to claim SS, whether to work part time, where to live (Yonkers / NYC / rest of Westchester / NJ, or a later move) and whether to rent or buy. Changes stay generic and data-driven so they can go upstream.

Read these first, in this order:

1. `fork-notes/phase1-revised.md` — what is done, what was decided and why, measured stakes, revised priorities. Its last section ("Reassessment") is the current plan.
2. `fork-notes/phase0/phase0-scenarios.md` — how the household's scenarios are run (`owlcli run` / `owlcli compare`).
3. `PROGRESS.md` (repo root, fork-only like this file): the running log of what is done, filed and next. Update it at the end of every work session and commit it with the work.

## State (2026-10-07)

- Branch `claude/nifty-tesla-gbq1wt` (2026-10-06/07), continued from `claude/project-thread-u0d9t0` (envelope model), from `claude/project-thread-qx5fy0` and earlier (`-v39073`, `optimistic-darwin-n5xykl`, `relaxed-turing-xzrv89`, `inspiring-rubin-f0a0p9`), merged with upstream `dev` at `5dd1623` (2026.10.8 plus one fix; `main` is behind it). Upstream sometimes lands a fix on `main` before `dev`: check both when syncing. Since 2026-10-07 (Phase 1 done) the fork's own `main` carries all of this work (fast-forwarded to the branch); a new session usually gets its own branch name: start it from `origin/main`, or from a later `claude/...` branch if `main` is behind it.
- Fork work beyond upstream:
  - typed state params (`StateTaxParams`; `st_taxParams` and `st_schedule` return it, where upstream returns a tuple and a dict; flag fields use upstream's dict keys `conv_ok_n`, `tax_ss_n`, `pension_eligible_n`, `fed_sd_n`, `senior_bonus_n`);
  - SC-loop registry `_SC_PARAMS`;
  - moves beyond upstream's one (#159): several, each with an optional locality, as `residency.Residence(year, state, locality)` in `Plan.state_moves` (upstream: `(year, state)` pairs, one move). Plan attribute names follow upstream's (`st_*_n` flags, `_states_n()`); the UI edits the first move and keeps the rest from the file;
  - local tax (`basic_info.locality`, `tax_local.py`, `data/taxes_local.toml`: NYC, Yonkers);
  - NY benefit recapture, loop mode (`tax_state.state_recapture`);
  - NJ retirement-income exclusion (lines 28a-28c) as a MILP: tier binaries `zx` with disaggregated income copies `rxl`/`rxb` (`Plan._add_state_tiered_exclusion`), free only near the ceilings, capped at `RX_NODE_LIMIT` (20,000 HiGHS nodes; MOSEK 60 s) without `maxTime`; a local-search family (`localsearch.FAMILIES`); data `retirement_exclusion_*` in `taxes_state.toml`;
  - summary and Taxes-sheet breakdown; MCP explain adapted.
- Upstream (maintainer responses as of 2026-10-07): fixed upstream and merged, taking theirs: #161, #164, #165 (also Medicaid at no premium up to 138% FPL), #166, #168, #169; #159 implemented as one move, no local tax (fork keeps its extension). #167 (partial first year) documented upstream (`22ec12f`), left open for a short first period; our reply posted (`fork-notes/issue-partial-first-year-reply.md`). #163 (cycle selection) on hold. #170 (envelope model) and #171 (pinned loop), one conversation, declined in favor of `breakpointMethod = "local-search"` (2026.10.6); our findings `fork-notes/local-search/README.md`, reply posted (`fork-notes/issue-local-search-reply.md`); all three points adopted in `785217c` (tie keeps the consistent plan, which was the fork's rule and is now theirs; an unchanged problem is not searched again; morgan's measure acknowledged). Still open from before: #158 (NY recapture; stock-`dev` patch `fork-notes/issue-ny-recapture.patch`, refreshed on `5dd1623`; follow-up comment posted 2026-10-06, `issue-ny-recapture-update.md`; no reply on #158 yet), #160 (NJ exclusion; upstream keeps state taxes a pure LP). Earlier fixes upstream: #147, #149, #155, #157, #162. Drafts are in `fork-notes/issue-*.md`.
- Dropped by decision: recapture optimize mode (conversion-cap grid showed zero regret; lifetime recapture $81–6.4k); the envelope model as an upstream feature (#171 declined; it stays a fork-notes screen).
- Not filed: docs/paper drift (`fork-notes/issue-docs-loop-and-paper.md`); upstream rewrote parts of `papers/owl.tex` in 2026.10.6-7, so recheck it before filing.
- **Next:** Phase 2, housing ledger and property tax (NJ property tax deduction up to $15,000 / credit attaches there). NJ-1040 instructions: `https://www.nj.gov/treasury/taxation/pdf/current/1040i.pdf`, past years under `pdf/other_forms/tgi-ee/<year>/1040i.pdf` (`www.state.nj.us` is blocked by the proxy).

## Setup (the container is ephemeral; redo each session)

```bash
uv sync --python 3.11            # uv's default picked a 3.14 rc that breaks pydantic
git remote add upstream https://github.com/mdlacasse/Owl.git; git fetch upstream
uv pip install --python .venv/bin/python pypdf   # only for reading tax PDFs
```

- Tests: `.venv/bin/python -m pytest -n 4 -q -p no:cacheprovider`. About 6 min on 4 cores. 2818 passed / 1 skipped on 2026-10-07 after merging `5dd1623`.
- Lint: `.venv/bin/python -m flake8 src tests ui --max-line-length=120`. Upstream's own long lines (`localsearch.py:31`, `config/schema.py:388` on `5dd1623`) are theirs; leave them.
- To keep editing while the suite runs, run it in a `git worktree` with `.venv` symlinked in.

## Conventions

- **Upstream:** CONTRIBUTING says branch from and target `dev`. The maintainer implements fixes himself from issues, crediting the reporter. He has not merged our PRs. So send each finding as an issue with a repro on stock `dev` and a minimal patch verified against stock `dev`, and large features as a design issue. Draft issues in `fork-notes/`; the user files them.
- **Syncing:** `git merge upstream/dev` with a merge commit. Never rebase or force-push this branch. When upstream lands one of our fixes, take theirs and drop our duplicate code and tests.
- **Commits:** CONTRIBUTING tags (`[feat]`, `[fix]`, `[docs]` …, `[no ci]` for docs-only).
- **Privacy:** the fork is public. Real balances, PIAs and wages live only in `otherFiles/` (gitignored by upstream itself). `fork-notes/phase0/` holds templates with placeholders.
- **Evidence:** the user wants claims checked against primary sources, and wants each statement to say whether it was verified or recalled. Tax rules come from the state's own instructions (we read IT-201-I 2018/2021/2024/2025 and NYS-50-T-* 2026 from tax.ny.gov). Data files carry a `description`/comment saying where each number comes from. Repro output pasted into an issue must come from a real run.

## Gotchas found the hard way

- **`owlcli compare`:** `--set` applies to the variant only, so the base case file must be complete.
- **Cliffs belong in the MILP, not the loop:** a loop-fed tier for the NJ exclusion 2-cycled and accepted a plan that undercharged its own tax by $13.9k. A big-M on income made each MILP 4-6 s; the disaggregated form takes about 1 s. Never add the same column twice to one row (`abcapi` does not merge duplicates; HiGHS crashed with "double free").
- **NJ exclusion solve limits:** tier binaries are free only in years within `RX_WINDOW` (1.5x the top ceiling) of the previous iterate's income (`RXF_n`, an SC parameter; iteration 0 runs without the exclusion). Without `maxTime`, a HiGHS MILP carrying them stops at `RX_NODE_LIMIT` (20,000 nodes; HiGHS says "Solution limit reached"), warns with the gap, and later iterations keep its tiers (`_rx_fixed`; not inside local search); `solverGap` reports that MILP's gap. Node caps give the same plan on any machine (the old 60 s cap did not); MOSEK still uses 60 s. With `maxTime`, there is no node cap.
- **Upstream's local search and fork binaries:** `localsearch.FAMILIES` must list every binary block the search may meet. A block left out is relaxed by the LP start, and the search then returns that fractional plan (it did, for `zx`, until 2026-10-06). Upstream sends its other non-family binaries (`zssa`, `zo`) to branch-and-bound before searching.
- **Loop noise:** under the default self-consistent loop, scenario differences under about 1% can come from the loop settling on different fixed points, and can have the wrong sign (NJ vs NY at $1.5M: loop −$191/yr, local search +$430, exact LP +$1,006; PROGRESS.md). For decisions, compare variants with `breakpointMethod="local-search"` (seconds to minutes each; never worse than the loop), cross-check with the exact LP (`withMedicare="None"`, `withSSTaxability=0.85`), and treat differences smaller than the spread between the two as unresolved. Local search overrides a pinned SS fraction with the IRS formula.
- **Degenerate tests:** in a fixed-income `maxSpending` test plan, first-year income can cap spending, and later taxes then cost nothing. Use `maxBequest` with `netSpending` instead.
- **Earnings test:** not modeled. In scenarios where one spouse works, optimize SS ages only for the one who stops (`withSSAges=["Name"]`).
- **`pkill -f <pattern>`** can kill the shell running it. Kill by PID instead.
- **TOML arrays must be homogeneous** for the `toml` package: write `[[100000.0, 100.0], [125000.0, 37.5]]`, not mixed ints and floats.
- **Owl units:** `setAccountBalances` takes thousands of dollars; `setPension`/`setSocialSecurity` take monthly amounts. Test plans with balances entered in dollars (1000x too large) came back "infeasible" with no other hint.
- **TOML encoding:** files must be UTF-8. A Windows-1252 em dash stops `owlcli` with a `UnicodeDecodeError`.
- **State parameters are per year:** `st_tax_ss`, `st_conv_ok`, `st_fed_sd` and the other flags are arrays, because the state can change mid-plan. `st_T_n` is state + recapture + local; `st_recap_n` and `lt_T_n` are its parts. `st_agi_n` is state income before the NJ exclusion (its tiers are set on it); `st_rx_n` is the exclusion claimed.
