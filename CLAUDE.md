# CLAUDE.md — fork `fmateoc/Owl` (not part of upstream)

This fork extends Owl (upstream `mdlacasse/Owl`) so that one NY-metro couple can decide when to retire, when to claim SS, whether to work part time, where to live (Yonkers / NYC / rest of Westchester / NJ, or a later move) and whether to rent or buy. Changes stay generic and data-driven so they can go upstream.

Read these first, in this order:

1. `fork-notes/phase1-revised.md` — what is done, what was decided and why, measured stakes, revised priorities. Its last section ("Reassessment") is the current plan.
2. `fork-notes/phase0/phase0-scenarios.md` — how the household's scenarios are run (`owlcli run` / `owlcli compare`).
3. The user may upload `otherFiles/PROGRESS.md` (their running log; it never reaches git). If they do, update it there and send it back; it is gitignored.

## State (2026-10-02)

- Branch `claude/inspiring-rubin-f0a0p9`, merged with upstream `dev` at `a85ff76` (2026.10.1). A new session usually gets its own branch name: start it from this branch.
- Fork work beyond upstream:
  - typed state params and `indexed` (NY not indexed);
  - SC-loop registry `_SC_PARAMS`;
  - mid-plan moves (`basic_info.moves`, `residency.py`);
  - local tax (`basic_info.locality`, `tax_local.py`, `data/taxes_local.toml`: NYC, Yonkers);
  - NY benefit recapture, loop mode (`tax_state.state_recapture`);
  - summary and Taxes-sheet breakdown;
  - MCP explain adapted.
- Upstream issues filed by the user and open: #157 (NY not indexed), #158 (NY recapture), #159 (design proposal: moves + local tax, six questions for the maintainer). Drafts are in `fork-notes/issue-*.md`. Earlier ones were fixed upstream (#147, #149, #155), and our copies were dropped in the merges.
- Dropped by decision: recapture optimize mode. A conversion-cap grid showed zero regret, and lifetime recapture was $81–6.4k.
- **Next:** NJ retirement-income exclusion (income cliffs), as a loop quantity like recapture, built from `st_agi_n`. Read the NJ-1040 instructions first: `nj.gov` is on the allow list. After that, Phase 2: housing ledger and property tax.

## Setup (the container is ephemeral; redo each session)

```bash
uv sync --python 3.11            # uv's default picked a 3.14 rc that breaks pydantic
git remote add upstream https://github.com/mdlacasse/Owl.git; git fetch upstream
uv pip install --python .venv/bin/python pypdf   # only for reading tax PDFs
```

- Tests: `.venv/bin/python -m pytest -n 2 -q -p no:cacheprovider`. About 4–7 min, 2674 passed / 1 skipped at the last merge.
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
- **Loop noise:** under the default self-consistent loop, scenario differences under about 1% can come from the loop settling on different fixed points. For decisions, also run with `withMedicare="None"` and a pinned `withSSTaxability` (e.g. `0.85`) so the LP is exact.
- **Degenerate tests:** in a fixed-income `maxSpending` test plan, first-year income can cap spending, and later taxes then cost nothing. Use `maxBequest` with `netSpending` instead.
- **Earnings test:** not modeled. In scenarios where one spouse works, optimize SS ages only for the one who stops (`withSSAges=["Name"]`).
- **`pkill -f <pattern>`** can kill the shell running it. Kill by PID instead.
- **TOML encoding:** files must be UTF-8. A Windows-1252 em dash stops `owlcli` with a `UnicodeDecodeError`.
- **State parameters are per year:** `st_tax_ss`, `st_conv_ok`, `st_fed_sd` and the other flags are arrays, because the state can change mid-plan. `st_T_n` is state + recapture + local; `st_recap_n` and `lt_T_n` are its parts.
