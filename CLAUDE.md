# CLAUDE.md — fork `fmateoc/Owl` (not part of upstream)

This fork extends Owl (upstream `mdlacasse/Owl`) so that one NY-metro couple can decide when to retire, when to claim SS, whether to work part time, where to live (Yonkers / NYC / rest of Westchester / NJ, or a later move) and whether to rent or buy. Changes stay generic and data-driven so they can go upstream.

Read these first, in this order:

1. `fork-notes/phase1-revised.md` — what is done, what was decided and why, measured stakes, revised priorities. Its last section ("Reassessment") is the current plan.
2. `fork-notes/phase0/phase0-scenarios.md` — how the household's scenarios are run (`owlcli run` / `owlcli compare`).
3. `PROGRESS.md` (repo root, fork-only like this file): the running log of what is done, filed and next. Update it at the end of every work session and commit it with the work.

## State (2026-10-04)

- Branch `claude/project-thread-qx5fy0` (2026-10-04: model-review fixes for ACA 133-150% band, survivor never claimed, cost basis, SS-age taxes) on top of `claude/project-thread-v39073` (continued from `claude/optimistic-darwin-n5xykl`, from `claude/relaxed-turing-xzrv89`, from `claude/inspiring-rubin-f0a0p9`), merged with upstream `main` at `c58228e` (2026.10.4; contains `dev` `c1e5619`). Upstream sometimes lands a fix on `main` before `dev`: check both when syncing. A new session usually gets its own branch name: start it from the latest of these.
- Fork work beyond upstream:
  - typed state params (`StateTaxParams`, with upstream's indexing flags and credits as `credit_n`);
  - SC-loop registry `_SC_PARAMS`;
  - mid-plan moves (`basic_info.moves`, `residency.py`);
  - local tax (`basic_info.locality`, `tax_local.py`, `data/taxes_local.toml`: NYC, Yonkers);
  - NY benefit recapture, loop mode (`tax_state.state_recapture`);
  - NJ not indexed, NJ exemptions; NJ retirement-income exclusion (lines 28a-28c) as a MILP: tier binaries `zx` with disaggregated income copies `rxl`/`rxb` (`Plan._add_state_tiered_exclusion`), free only near the ceilings, 60 s default cap; data `retirement_exclusion_*` in `taxes_state.toml`;
  - summary and Taxes-sheet breakdown;
  - MCP explain adapted.
- Upstream issues filed by the user and open: #158 (NY recapture), #159 (design proposal: moves + local tax, six questions for the maintainer), #160 (NJ exclusion; maintainer keeps state taxes a pure LP, so NJ stays unexcluded upstream and the fork keeps its MILP; our reply is posted, see PROGRESS.md), #161 (ACA optimize infeasible), #163 (SC-loop cycle selection). #162 (bracket order) was fixed upstream in `3fca646` (2026.10.4) with our patch verbatim and merged here; the fork keeps its copy, which also covers local brackets. #157 (NY/NJ not indexed, with the user's NJ addendum) was fixed upstream in `3c88ce1` (2026.10.3) and merged here, taking theirs. Drafts are in `fork-notes/issue-*.md`. Earlier ones were fixed upstream (#147, #149, #155), and our copies were dropped in the merges.
- Dropped by decision: recapture optimize mode. A conversion-cap grid showed zero regret, and lifetime recapture was $81–6.4k.
- Drafts behind filed issues: bracket order #162 (`fork-notes/issue-bracket-order.md`), ACA optimize infeasibility #161 (`fork-notes/issue-aca-optimize-infeasible.md`), SC-loop cycle selection #163 (`fork-notes/issue-cycle-selection.md`), each with a `.patch` verified on stock `dev`; the #160 reply (`fork-notes/issue-nj-retirement-exclusion-reply.md`).
- Model review of paper vs code: `fork-notes/model-review/README.md` (findings and repro scripts). Fixed so far: bracket order, ACA infeasible band, ACA 133-150% band, survivor of a worker who never claimed, cost basis (reinvested income, gain in equities), SS-age MILP taxes. Filed upstream by the user on 2026-10-04 (numbers not recorded yet): those four plus partial first year and ACA optimize rates. Not filed: docs/paper drift (`fork-notes/issue-docs-loop-and-paper.md`).
- **Next:** Phase 2, housing ledger and property tax (NJ property tax deduction up to $15,000 / credit attaches there). NJ-1040 instructions: `https://www.nj.gov/treasury/taxation/pdf/current/1040i.pdf`, past years under `pdf/other_forms/tgi-ee/<year>/1040i.pdf` (`www.state.nj.us` is blocked by the proxy).

## Setup (the container is ephemeral; redo each session)

```bash
uv sync --python 3.11            # uv's default picked a 3.14 rc that breaks pydantic
git remote add upstream https://github.com/mdlacasse/Owl.git; git fetch upstream
uv pip install --python .venv/bin/python pypdf   # only for reading tax PDFs
```

- Tests: `.venv/bin/python -m pytest -n 2 -q -p no:cacheprovider`. About 4–7 min. 2724 passed / 1 skipped on 2026-10-04 (with the model-review fixes).
- Lint: `.venv/bin/python -m flake8 src tests ui --max-line-length=120`.
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
- **NJ exclusion solve limits:** tier binaries are free only in years within `RX_WINDOW` (1.5x the top ceiling) of the previous iterate's income (`RXF_n`, an SC parameter; iteration 0 runs without the exclusion). Without `maxTime`, a MILP carrying them stops at `RX_TIME_LIMIT` (60 s), warns with the gap, and later iterations keep its tiers (`_rx_fixed`); `solverGap` reports that MILP's gap. Results that hit the cap depend on CPU speed, so don't time-cap runs you compare across machines; pass a large `maxTime` for decisions.
- **Loop noise:** under the default self-consistent loop, scenario differences under about 1% can come from the loop settling on different fixed points. For decisions, also run with `withMedicare="None"` and a pinned `withSSTaxability` (e.g. `0.85`) so the LP is exact.
- **Degenerate tests:** in a fixed-income `maxSpending` test plan, first-year income can cap spending, and later taxes then cost nothing. Use `maxBequest` with `netSpending` instead.
- **Earnings test:** not modeled. In scenarios where one spouse works, optimize SS ages only for the one who stops (`withSSAges=["Name"]`).
- **`pkill -f <pattern>`** can kill the shell running it. Kill by PID instead.
- **TOML arrays must be homogeneous** for the `toml` package: write `[[100000.0, 100.0], [125000.0, 37.5]]`, not mixed ints and floats.
- **Owl units:** `setAccountBalances` takes thousands of dollars; `setPension`/`setSocialSecurity` take monthly amounts. Test plans with balances entered in dollars (1000x too large) came back "infeasible" with no other hint.
- **TOML encoding:** files must be UTF-8. A Windows-1252 em dash stops `owlcli` with a `UnicodeDecodeError`.
- **State parameters are per year:** `st_tax_ss`, `st_conv_ok`, `st_fed_sd` and the other flags are arrays, because the state can change mid-plan. `st_T_n` is state + recapture + local; `st_recap_n` and `lt_T_n` are its parts. `st_agi_n` is state income before the NJ exclusion (its tiers are set on it); `st_rx_n` is the exclusion claimed.
