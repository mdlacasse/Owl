<!--
Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
SPDX-License-Identifier: CC-BY-NC-SA-4.0
This documentation is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0; see LICENSE-docs in the repository root.
-->

# Owl MCP Server — AI Integration

Owl ships with an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server
that lets any compatible AI assistant — Claude Desktop, Claude Code, Gemini CLI, Cursor, and others —
call Owl directly as a tool. The AI can discover cases, inspect configurations, run
optimizations, and compare scenarios through natural conversation.

## Tools exposed

| Tool | Description | Solves? |
|------|-------------|---------|
| `list_cases(directory)` | Enumerate `.toml` case files in a directory | No |
| `explain_case(filename, overrides)` | Describe a case: individuals, balances, fixed assets, debts, opening balance sheet, income, options | No |
| `list_rate_models(category)` | Enumerate return models with parameters | No |
| `list_mortality_tables()` | Actuarial mortality tables for longevity risk sampling | No |
| `convert_ss_benefit(birth_year, claiming_age, ...)` | Convert between SS PIA and actual benefit at a claiming age | No |
| `list_contribution_limits(birth_years, tax_year)` | IRS contribution-limit ceilings (incl. 50+ and 60-63 catch-up) by birth year | No |
| `run_case(filename, overrides, ...)` | Solve and return full JSON results | Yes |
| `compare_cases(filename, overrides, ...)` | Solve base + variant, return delta | Yes |
| `compare_to_baseline(filename or params, baseline_policies)` | Quantify the dollar value of optimization vs a conventional baseline (no Roth conversions, Social Security at stated ages, taxable-first withdrawal ordering) | Yes (×2) |
| `explain_results(filename or params)` | Explain WHY the plan looks as it does: shadow prices of goals and rules, Roth conversion rationale and binding caps, tax-bracket fill, account depletion order | Yes |
| `run_from_params(names, birth_years, ...)` | Build and solve from structured parameters — no TOML file needed | Yes |
| `save_case(names, birth_years, ...)` | Save structured parameters to TOML + HFP Excel for reproducibility | No |
| `run_stochastic(scenario_method, ...)` | Spending efficient frontier over historical or Monte Carlo scenarios | Yes (×N) |
| `run_longevity_stochastic(sexes, ...)` | Spending frontier with joint market + random lifespan sampling | Yes (×N) |
| `run_historical(ystart, yend, ...)` | Backtest across historical sequences — distribution of optimal outcomes | Yes (×N) |
| `run_monte_carlo(n_scenarios, ...)` | Monte Carlo simulations — distribution of optimal outcomes | Yes (×N) |

`run_case` and `compare_cases` accept optional `solver`, `max_time`, and `seed`
arguments. MIP gap tolerance and other solver options can be set via `overrides`
(e.g. `solver_options.gap=1e-4`), same as `owlcli run --set`. The `overrides`
argument uses `KEY.PATH=VALUE` syntax identical to `owlcli run --set` (values are
JSON-parsed).

**File paths:** The MCP server runs in its own working directory. Use **absolute
paths** for `directory`, `filename`, and `output_dir` (e.g. `/path/to/Owl/examples/`).

`run_from_params`, `save_case`, `run_stochastic`, `run_longevity_stochastic`,
`run_historical`, and `run_monte_carlo` accept the full set of plan parameters
directly, eliminating the need to write a TOML file first.

**Unit conventions:** All monetary balances and solver limits are in full dollars (\$);
time-series amounts (wages, contributions, big-ticket items) are in \$ per year; Social
Security is the monthly PIA from your SSA statement (\$ per month); pensions are in
\$ per month. Asset allocation arrays are `[equities, corporate_bonds, t_notes, cash]`
in percent. Fixed user rates (`rate_method="user"`) use
`[equities, corporate_bonds, t_notes, inflation]` in percent.

**Social Security PIA vs. actual benefit:** `ss_monthly_pias` must be the Primary
Insurance Amount (the benefit at Full Retirement Age, from the SSA statement) — NOT
the check amount someone describes receiving if they claimed before or after FRA
(e.g. "I'm 65 and I get $2,800/month"). If the user only knows their actual benefit
at a given claiming age, call `convert_ss_benefit` first to back out the PIA.

**Assumed defaults:** the solve tools report material assumptions made for omitted
parameters (state, cost basis, return model, allocation, Social Security, pre-65 ACA
coverage, ...) in an `assumed_defaults` field of the response, so the AI can relay
them and ask for the true values when they matter.

## Prompt and resources

Besides tools, the server exposes an interview script and reference documents for
clients that support MCP prompts and resources (e.g., Claude Desktop shows prompts
as commands and lets you attach resources to the conversation):

| Kind | Name / URI | Content |
|------|------------|---------|
| Prompt | `owl_intake` | Interview script for gathering plan data: must-ask questions (state, balances, Social Security, work status, pre-65 health coverage), ask-when-applicable items, safe-to-assume defaults, and unit conventions |
| Resource | `owl://intake-checklist` | The same intake checklist, readable as a document |
| Resource | `owl://modeling-capabilities` | Reference table of every modeled component with its assumptions and limitations |

**Parameter reference** (all optional unless marked *required*):

| Category | Parameter | Description |
|----------|-----------|-------------|
| **Required** | `names` * | Person names, e.g. `["Alice", "Bob"]` |
| | `birth_years` * | Birth years, e.g. `[1963, 1961]` |
| | `life_expectancy` * | Life expectancy in years per person, e.g. `[90, 87]` |
| | `taxable` * | Taxable account balances in \$ per person |
| | `tax_deferred` * | Tax-deferred (401k/IRA/403b) balances in \$ per person |
| | `roth` * | Roth account balances in \$ per person |
| **Balances** | `hsa` | HSA balances in \$ per person |
| | `cost_basis` | Taxable cost basis in \$ per person. If omitted, realized gains are modeled from current-year appreciation only (flagged in `assumed_defaults`) |
| **Social Security** | `ss_monthly_pias` | Monthly PIA per person from SSA statement (\$ per month) |
| | `ss_ages` | SS claiming ages per person (e.g. `[67, 67]`) |
| **Pensions** | `pension_monthly_amounts` | Monthly pension in \$ per month per person |
| | `pension_ages` | Pension commencement ages per person |
| | `pension_indexed` | CPI-linked flags per person, e.g. `[True, False]` |
| | `pension_survivor_fractions` | Survivor benefit fractions (0–1) per person, e.g. `[0.5, 0.0]` |
| **Time series** | `wages` | Wage streams: `[{"person":0,"annual_amount":90_000,"end_year":2032}]` |
| | `contributions` | Retirement contributions; `account` is `taxable`, `tax_deferred`, `roth`, or `hsa`. Use `list_contribution_limits` to find IRS max amounts (incl. catch-up) |
| | `big_ticket_items` | One-time or recurring extra expenses reducing spending budget |
| **Assets & debts** | `debts` | Amortizing loans: `{"label","type","balance","rate","years_remaining"}` |
| | `fixed_assets` | Assets to sell: `{"label","type","value","basis","sell_year","commission"}` |
| | `spias` | SPIAs: `{"person","buy_year","premium","monthly_income","indexed","survivor_fraction"}` |
| **Plan settings** | `state` | Two-letter US state code for income tax. Strongly recommended; if omitted, TX (no state tax) is assumed and flagged in `assumed_defaults` |
| | `objective` | `"maxSpending"` (default) or `"maxBequest"` |
| | `survivor_fraction` | Surviving-spouse spending as % of couple spending (default 60) |
| | `balance_date` | Date balances were recorded as `"MM-DD"` or `"YYYY-MM-DD"` (default: today) |
| | `heirs_tax_rate` | Heirs' marginal income tax rate in % applied to inherited tax-deferred assets (default 30) |
| | `liquidation_tax_rate` | Ordinary tax rate in % on tax-deferred/HSA if liquidated, for the liquid balance sheet (default 24) |
| | `liquidation_capgains_rate` | Capital-gains tax rate in % on fixed-asset disposition, for the liquid balance sheet (default 15) |
| **Rate model** | `rate_method` | Return model name (use `list_rate_models`). If omitted, fixed `"conservative"` rates are assumed and flagged in `assumed_defaults` |
| | `rate_values` | Fixed rates `[equities, corp_bonds, t_notes, inflation]` in % for `rate_method="user"` |
| | `rate_frm` | First year of historical rate window (e.g. `1966`) |
| | `rate_to` | Last year of historical rate window |
| | `rate_params` | Extra rate model params dict, e.g. `{"bootstrap_type":"block","block_size":5}` |
| | `constrain_mean` | Pin stochastic series means to historical averages (isolates SOR risk) |
| **Allocation** | `initial_allocation` | Starting `[equities, corp_bonds, t_notes, cash]` in % (default `[60,40,0,0]`) |
| | `final_allocation` | Ending allocation % (default `[40,60, 0,0]`) |
| | `interpolation_method` | Glide-path shape: `"linear"` (default) or `"s-curve"` |
| | `interpolation_center` | S-curve midpoint in years from plan start (default 15) |
| | `interpolation_width` | S-curve transition half-width in years (default 5) |
| **Spending profile** | `spending_profile` | `"smile"` (default) or `"flat"` |
| | `smile_dip` | Slow-go spending dip as % below go-go peak (default 15) |
| | `smile_increase` | No-go medical cost growth over full horizon in % (default 12) |
| | `smile_delay` | Go-go years to hold flat before smile dip begins (default 0) |
| **Optimization** | `net_spending` | Annual spending floor in $/year when `objective="maxBequest"` |
| | `min_taxable_balance` | Emergency-fund floor in \$ per person, e.g. `[15_000]` |
| | `bequest` | Target estate in today's \$ for `maxSpending` objective |
| | `start_roth_year` | 4-digit year before which Roth conversions are disabled |
| | `no_roth_person` | Name of individual excluded from all Roth conversions (couples only) |
| | `max_roth_conversion` | Annual per-person Roth conversion cap in $/year |
| | `roth_conversions` | Per-cell conversion overrides `[{"person","year","amount"}]`; enforced only with `use_roth_conv_overrides=True` (positive pins, negative forces zero) |
| | `use_roth_conv_overrides` | Turn the `roth_conversions` entries into hard per-year overrides |
| | `swap_roth_converters_first` / `swap_roth_converters_year` | Switch which spouse converts starting at a given year (couples) |
| | `optimize_ss_ages` | SS claiming-age MIP (62–70, monthly): `True`/`"all"`, a name, or a list of names |
| | `with_medicare` | IRMAA mode: `"none"`, `"loop"` (default), or `"optimize"` (embed in MIP) |
| | `with_aca` | ACA premium mode: `"none"`, `"loop"` (default when `slcsp` set), or `"optimize"` |
| | `aca_start_year` | Calendar year ACA coverage begins (e.g. `2028`) |
| | `previous_magis` | Prior-year MAGI per person in $ for Medicare IRMAA (first 2 plan years) |
| | `solver` | `"HiGHS"` or `"MOSEK"` (default: best available) |
| | `max_time` | Solver time limit in seconds |
| **Policy scenarios** | `slcsp` | Annual ACA Silver benchmark premium in $/year for pre-65 individuals |
| | `ss_trim_pct` | SS trust fund haircut in % (e.g. `23` for SSA trustees baseline) |
| | `ss_trim_year` | Year SS benefit reduction begins (e.g. `2033`) |
| | `obbba_expiration_year` | Year OBBBA tax rates sunset to pre-TCJA levels (default `2032`) |
| | `dividend_rate` | Taxable account annual dividend yield in % (default `1.8`) |
| **Stochastic only** | `scenario_method` | `"historical"` (default) or `"mc"` (Monte Carlo) |
| | `target_success_rate_pct` | Desired shortfall-free percentage, in `(1, 100]`, e.g. `90` (default) |
| | `n_scenarios` | Number of Monte Carlo draws (mc mode, default `200`); ignored in historical mode |
| | `ystart` / `yend` | Historical window start/end years (historical mode) |
| | `seed` | Random seed for reproducibility |
| **`compare_to_baseline` only** | `baseline_policies` | Restrictions defining the baseline (default all): `"no_roth_conversions"`, `"no_ss_age_optimization"`, `"taxable_first_ordering"` |
| | `seed` | Shared rate-series seed applied to both runs so stochastic methods see identical markets (auto-generated when omitted) |
| **`save_case` only** | `output_dir` | Directory where `Case_*.toml` and `HFP_*.xlsx` are written (default: `.`) |
| | `case_name` | Override the auto-generated filename stem (default: names joined with `+`, e.g. `alice+bob`) |

**Balance sheet & net worth in results:** `run_case` and `run_from_params` return a
full balance-sheet view alongside the cash-flow metrics. The top-level `summary`
block reports the **opening balance sheet** (`net_worth_start_nominal` /
`_today_dollars`, `liquid_net_worth_start_*`, `fixed_assets_start_nominal`,
`debt_start_nominal`, `deferred_income_tax_start_nominal`) plus the liquidation
assumptions (`liquidation_tax_rate`, `liquidation_capgains_rate`, as fractions). Each
`by_year` entry adds `fixed_assets`, `debt`, `net_worth`, `deferred_income_tax`,
`disposition_costs`, and `liquid_net_worth`. (Note: `portfolio_total` in `by_year` is
savings accounts only — use `net_worth` for the full picture.) **Net worth** =
savings + fixed assets − debt; **liquid net worth** additionally nets the future
income tax owed on tax-deferred/HSA balances and the disposition costs (commission +
capital-gains tax) of fixed assets. `explain_case` reports the same opening
balance-sheet view from the unsolved inputs, plus the `fixed_assets` and `debts`
lists read from the HFP workbook.

**Two strategy-analysis tools:**

`compare_to_baseline` answers *"what is the optimization actually worth in dollars?"*
It solves the same case twice — fully optimized, and restricted to a conventional
baseline strategy (no Roth conversions, Social Security at the stated ages,
taxable-first withdrawal ordering; select restrictions via `baseline_policies`) — and
reports the advantage in today's dollars: extra annual and lifetime spending, extra
final bequest, and the tax/premium difference. The baseline is a restriction of the
optimized problem, so the advantage is a certified lower bound (up to solver gap).

`explain_results` answers *"why does the plan look the way it does?"* It solves with
dual extraction and returns LP shadow prices — the lifetime-spending cost per dollar
of bequest floor, the value of an extra dollar of income in each year, the cost of
each forced RMD dollar — plus the Roth conversion schedule with binding-cap values,
per-year federal bracket fill and headroom, and the account depletion order.
Sensitivities are marginal and hold bracket selections fixed.

**Three distinct stress-test tools:**

`run_stochastic` pre-commits to a spending level and asks: *across N scenarios, how
often does it succeed?* Returns the spending efficient frontier (spending vs.
probability of success) at a requested target success rate.
Use `scenario_method="historical"` (default, sweeps 1928–present) or `"mc"` with a
stochastic `rate_method`.

`run_historical` backtests the plan's full flexibility across every historical start
year in `[ystart, yend]`.  Each year the optimizer solves optimally for that sequence —
no pre-committed spending.  Returns a distribution (`min/p10/median/p90/max`) and a
per-year breakdown.  Use this to see which decades were hardest and what the optimizer
could have achieved in each.

`run_monte_carlo` is the same as `run_historical` but with randomly generated rate
sequences instead of historical ones.  Requires a stochastic `rate_method` (default
`"gmm"`).  All methods that draw from or are calibrated to historical data — `gmm`,
`hmm`, `garch_dcc`, `vector_ar`, and the `historical_*` family — accept `rate_frm`
and `rate_to` to define the calibration window; the `historical_*` methods require
these parameters, while the others default to the full 1928–present record.  The
bootstrap family (`historical_bootstrap`) supports additional resampling options via
`rate_params`, e.g. `{"bootstrap_type":"block","block_size":5}`.

---

## Claude Desktop

Add Owl to Claude Desktop's MCP server list by editing
`claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Recommended: via `uv` (works everywhere)

```json
{
  "mcpServers": {
    "owl": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/Owl", "owlcli", "serve"]
    }
  }
}
```

Replace `/path/to/Owl` with the absolute path to the Owl repository. `uv`
activates the correct virtual environment automatically — no PATH setup needed.

### Alternative: if `owlcli` is already on your PATH

```json
{
  "mcpServers": {
    "owl": {
      "command": "owlcli",
      "args": ["serve"]
    }
  }
}
```

Restart Claude Desktop after saving. The tools appear automatically in the
conversation interface.

---

## Claude Code (CLI)

Add Owl as an MCP server using `uv` (recommended — works from any directory):

```bash
claude mcp add owl -- uv run --project /path/to/Owl owlcli serve
```

Or, if you always run Claude Code from within the Owl project directory:

```bash
claude mcp add owl -- uv run owlcli serve
```

Claude Code starts `owlcli serve` automatically when the tools are needed.
Verify the registration at any time:

```bash
claude mcp list
```

---

## Cursor

Cursor supports MCP in **Agent** mode (Composer). Add Owl once; the tools are then
available in any workspace.

### Option A — Settings UI (recommended)

1. Open **Cursor Settings** → **MCP** (or search “MCP” in settings).
2. Click **Add new MCP server** (or edit an existing entry).
3. Name it `owl` and use:

   - **Command:** `uv`
   - **Args:** `run --project /path/to/Owl owlcli serve`

   Replace `/path/to/Owl` with the absolute path to your Owl clone.

4. Save and confirm the server shows **Connected** (green status).
5. Open **Agent** chat and ask a retirement question — Cursor will call Owl tools
   automatically (e.g. `run_from_params`, `list_cases`).

If the server fails to start, click it in the MCP list to read stderr (solver logs
also go to stderr and do not break the MCP channel).

### Option B — Config file

Create or edit `~/.cursor/mcp.json` (user-wide, all projects):

```json
{
  "mcpServers": {
    "owl": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/Owl", "owlcli", "serve"]
    }
  }
}
```

For a **project-only** setup, put the same JSON in `.cursor/mcp.json` at the root
of the Owl repo (or your planning workspace) and use the repo’s absolute path in
`--project`.

### Alternative: `owlcli` already on PATH

If you installed Owl globally and `owlcli` is on your `PATH`:

```json
{
  "mcpServers": {
    "owl": {
      "command": "owlcli",
      "args": ["serve"]
    }
  }
}
```

### Verify it works

1. In **Settings → MCP**, `owl` should show **Connected**.
2. In Agent chat, try: *“List cases in `/path/to/Owl/examples/` using Owl.”*
   Use an **absolute path** — the MCP process may not resolve relative paths like
   `examples/` from the repo root.
3. Optional CLI check (Claude Code users): `claude mcp list` if you also use that
   client with the same `uv run ... owlcli serve` command.

Toggle the server off/on or restart Cursor if you change `mcp.json`.

---

## Gemini CLI

[Gemini CLI](https://github.com/google-gemini/gemini-cli) supports MCP servers over the
same stdio transport. Add Owl to its settings file — `~/.gemini/settings.json` for a
user-wide setup (all projects), or `.gemini/settings.json` at a project root for a
project-only setup:

```json
{
  "mcpServers": {
    "owl": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/Owl", "owlcli", "serve"]
    }
  }
}
```

If you always launch Gemini CLI from within the Owl project directory, you can drop
`--project /path/to/Owl` and use `"args": ["run", "owlcli", "serve"]`. If `owlcli` is
already on your PATH, use `"command": "owlcli"` with `"args": ["serve"]` instead.

Restart Gemini CLI after editing the file. List or inspect registered servers from within
the CLI with the `/mcp` command; the Owl tools are then called automatically when you ask a
retirement question. As with the other clients, pass **absolute paths** to tools like
`list_cases` — the MCP process may not resolve relative paths from the repo root.

---

## Testing the server (no AI required)

The official [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
(requires Node.js) opens a browser UI where you can call the tools manually,
launching the exact same command your AI client would:

```bash
npx @modelcontextprotocol/inspector uv run --project /path/to/Owl owlcli serve
```

(or `npx @modelcontextprotocol/inspector owlcli serve` if `owlcli` is on your
PATH). Open the printed `http://localhost:6274/...` URL and invoke `list_cases`,
`explain_case`, `run_case`, etc. directly. Useful for verifying the server
before connecting it to an AI.

---

## Other MCP-compatible clients

Any client that supports the MCP stdio transport uses the same pattern —
a command and argument list that launches `owlcli serve`. Common examples:

### VS Code (GitHub Copilot)

Requires **VS Code 1.99+** with the GitHub Copilot extension and Copilot Chat
enabled in agent mode.

Create `.vscode/mcp.json` in your workspace (or add to user `settings.json`
under the `"mcp"` key):

```json
{
  "servers": {
    "owl": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--project", "/path/to/Owl", "owlcli", "serve"]
    }
  }
}
```

Open the Copilot Chat panel, switch to **Agent** mode, and type `#owl` or
describe your scenario — Copilot will call the appropriate tool.

> **Tip:** If you keep Owl installed in a fixed location you can place
> `.vscode/mcp.json` inside the Owl repo itself and use
> `"${workspaceFolder}"` instead of a hard-coded path.

### VS Code (Cline extension)

[Cline](https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev)
is a popular open-source AI coding assistant for VS Code with full MCP support.

1. Install the **Cline** extension from the VS Code Marketplace.
2. Open the Cline panel → click the **MCP Servers** icon → **Edit MCP Settings**.
3. Add the `owl` entry:

```json
{
  "mcpServers": {
    "owl": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/Owl", "owlcli", "serve"]
    }
  }
}
```

The tools become available immediately — no restart required.

### Zed

Edit `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "owl": {
      "command": {
        "path": "uv",
        "args": ["run", "--project", "/path/to/Owl", "owlcli", "serve"]
      }
    }
  }
}
```

### Windsurf and other Codeium-based editors

Follow the same `mcpServers` format as [Cursor](#cursor) above.

---

## Embedded assistant (no MCP client required)

Self-hosted and Docker installations can also chat with an AI **inside the Owl web
UI**: an *Assistant* page that reuses the same tool implementations as this MCP
server in-process, and can additionally read the case currently open in the app
(read-only — it never modifies your session; scenarios are handed back as
`save_case` files loadable from the Create Case page).

The page is strictly opt-in and never appears on the hosted app. To enable it:

```bash
pip install "owlplanner[assistant]"      # or: uv sync --extra assistant
export OWL_ASSISTANT=1
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run ui/main.py
```

Optional environment variables: `OWL_ASSISTANT_MODEL` overrides the default model
(`claude-opus-4-8`); `OWL_ASSISTANT_BASE_URL` and `OWL_ASSISTANT_API_KEY` point the
assistant at a different endpoint and key (see *Using other or local models* below).
Conversations — including your case data when you ask about it — are sent to the
configured AI provider; the optimizer itself always runs locally.

### Choosing a model — cost vs. capability

The assistant is tool-heavy (sixteen tools with large schemas, multi-step chains
carrying your actual numbers), so model quality directly affects the correctness of
what it tells you. Approximate Anthropic list prices per million input/output tokens;
a typical chat turn with a couple of tool calls costs cents (the system prompt is
cache-marked, so repeat turns are cheaper):

| Model (`OWL_ASSISTANT_MODEL`) | $/MTok in/out | Notes |
|---|---|---|
| `claude-opus-4-8` (default) | $5 / $25 | Most capable; best tool use and explanations |
| `claude-sonnet-5` | $3 / $15 | Near-Opus on tool-driven work; the value pick |
| `claude-haiku-4-5` | $1 / $5 | Cheapest; fine for casual Q&A, weaker on long tool chains |

### Using other or local models

The assistant speaks the Anthropic Messages protocol, so any endpoint that serves
that format works with three variables:

```bash
export OWL_ASSISTANT_BASE_URL=https://provider.example.com/anthropic
export OWL_ASSISTANT_API_KEY=<that provider's key>
export OWL_ASSISTANT_MODEL=<that provider's model name>
```

The `OWL_ASSISTANT_*` variables are scoped to the assistant only. The SDK's own
`ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` are also honored (many providers'
Anthropic-compatible instructions use those names) — but they are global to every
Anthropic-SDK program in the same environment, so pointing them at a local proxy
would also redirect tools like Claude Code launched from that shell. Prefer the
`OWL_ASSISTANT_*` spelling; it takes precedence when both are set.

Several providers expose Anthropic-compatible endpoints natively. Everything else —
Google Gemini, OpenAI, Mistral, DeepSeek, local models — works through a
[LiteLLM](https://docs.litellm.ai) proxy, which serves the Anthropic `/v1/messages`
format in front of any backend and translates the tool calls.

**Free hosted option — Google Gemini.** Get a key from
[Google AI Studio](https://aistudio.google.com/apikey) (genuine free tier;
rate-limited, and on the free tier Google may use your data for training — it will
see the case numbers you chat about). Run the proxy in one terminal:

```bash
pip install 'litellm[proxy]'
export GEMINI_API_KEY=AIza...                   # the AI Studio key
litellm --model gemini/gemini-2.5-flash --port 4000
```

and point Owl at it in the shell that launches the app:

```bash
export OWL_ASSISTANT=1
export OWL_ASSISTANT_BASE_URL=http://localhost:4000
export OWL_ASSISTANT_API_KEY=anything           # LiteLLM accepts any key by default
export OWL_ASSISTANT_MODEL=gemini/gemini-2.5-flash
```

The `anthropic` package (`owlplanner[assistant]`) is still required — it is the
client speaking to the proxy — but no `ANTHROPIC_API_KEY` is needed; the Gemini key
lives with the proxy. `gemini/gemini-2.5-pro` is stronger on multi-step tool work;
model names evolve, so check the LiteLLM docs if one is rejected.

**Free local option — Ollama.** For fully local inference where nothing leaves your
machine, put the same proxy in front of [Ollama](https://ollama.com):

```bash
pip install 'litellm[proxy]'
litellm --model ollama/qwen3 --port 4000       # proxy in front of a local Ollama model

export OWL_ASSISTANT=1
export OWL_ASSISTANT_BASE_URL=http://localhost:4000
export OWL_ASSISTANT_API_KEY=anything           # LiteLLM accepts any key by default
export OWL_ASSISTANT_MODEL=ollama/qwen3
```

**Honest caveat:** any proxied provider runs through a protocol-translation layer, so
tool-calling fidelity is a notch below a native Anthropic connection, and small local
models are markedly weaker still at multi-step tool calling — expect occasional
misrouted parameters and shallower explanations, and double-check numbers against the
app before acting on them.

---

## Example interactions

Once connected, you can ask the AI naturally. The AI will pick the right tool,
translate your description into `--set` overrides, and interpret the results.

### Discovery

> *"What cases are in my examples folder?"*
> → calls `list_cases("examples/")`

> *"Describe the jack+jill case."*
> → calls `explain_case("examples/Case_jack+jill.toml")`

> *"What stochastic rate models are available?"*
> → calls `list_rate_models("stochastic")`

> *"I'm 61 and my wife is 54 — what's the most we can each put into our 401(k)s,
> IRAs, and HSA this year?"*
> → calls `list_contribution_limits(birth_years=[1965, 1972])`, then offers to add
> the max amounts as `contributions` entries in `run_from_params`/`save_case`

### Running a case from scratch

> *"I'm Martin, born in 1960, expecting to live to 90. I have \$200k in a
> taxable account, \$800k in a 401(k), and \$100k in a Roth IRA. My Social
> Security PIA is \$2,500/month and I'm claiming at 67. What's my optimal
> annual spending?"*
> → calls `run_from_params` directly — no TOML file needed

> *"Alice and Bob are both 62. Alice was born in 1963 and Bob in 1961. They
> expect to live to 90 and 87 respectively. Their combined savings are
> \$300k taxable, \$1.2M tax-deferred, and \$150k Roth. Alice's SS PIA is
> \$2,333/month claiming at 67, Bob's is \$2,667/month. Maximize their spending."*
> → calls `run_from_params` with two-person parameters

> *"Same as above but Alice earns \$90k/year until 2030, they have a \$350k
> mortgage at 3.5% with 20 years remaining, and a house worth \$800k
> (basis \$400k) they plan to sell in 2040 with 3% commission."*
> → calls `run_from_params` with `wages`, `debts`, and `fixed_assets`

> *"What's our net worth today and how does it evolve — and what would we
> actually keep after taxes if we liquidated everything?"*
> → calls `run_from_params` and reads `summary.net_worth_start_*` /
> `liquid_net_worth_start_*` and the `by_year` `net_worth` / `liquid_net_worth` series

> *"Robert is 69, born 1957, expects to live to 85. He has \$600k IRA,
> \$100k Roth, \$80k taxable, SS PIA \$2,400/month claiming at 68, lives
> in Ohio. He wants to keep at least \$15,000 in taxable as an emergency
> fund. Maximize his spending."*
> → calls `run_from_params` with `min_taxable_balance=[15000]`

> *"Save Alice and Bob's case to files so I can reload it later."*
> → calls `save_case` — writes `Case_alice+bob.toml` + `HFP_alice+bob.xlsx`

### Probability of success and efficient frontier

> *"What's the maximum I can spend with a 90% historical probability of success?"*
> → calls `run_stochastic` with `scenario_method="historical"`, `target_success_rate_pct=90`

> *"I'm Martin, born 1960, life expectancy 88. I have \$200k taxable, \$800k in a 401(k),
> \$100k Roth, SS PIA \$2,500/month claiming at 67. What can I safely spend at 90% confidence?"*
> → calls `run_stochastic` directly from flat parameters — no TOML needed

> *"Show me the trade-off between spending and success rate."*
> → calls `run_stochastic` and describes the `frontier` array

> *"How does the 90% spending change if I delay SS to 70?"*
> → calls `run_stochastic` twice via `compare_cases`-style overrides, reports delta

> *"What's safe spending at 90% success if we also account for longevity risk?"*
> → calls `list_mortality_tables`, then `run_longevity_stochastic` with `sexes=["F"]`,
> `scenario_method="mc"`, and a stochastic `rate_method` (e.g. `"gmm"`)

### Sensitivity and comparisons

> *"Run the jack+jill case and tell me the optimal spending."*
> → calls `run_case("examples/Case_jack+jill.toml")`

> *"How much does moving to Minnesota change their spending?"*
> → calls `compare_cases("examples/Case_jack+jill.toml", ["basic_info.state=MN"])`

> *"Compare delaying both SS claims to age 70 vs. the current plan."*
> → calls `compare_cases(..., ["fixed_income.social_security_ages=[70,70]"])`

> *"What's the impact of a more conservative asset allocation — 40/60 instead of 60/40?"*
> → calls `compare_cases` with allocation ratio overrides

> *"How does the plan change if I assume a 5% equity return instead of the default?"*
> → calls `compare_cases` with `rates_selection.method=user` and `values=[5,4,3,2]`

### Roth conversions and tax strategy

> *"How much should I convert to Roth each year to minimize lifetime taxes?"*
> → calls `run_case` with `optimization_parameters.objective=maxSpending` and
> Roth conversion options; AI explains the conversion schedule from `by_year`

> *"What's the tax cost of maximizing my estate vs. maximizing my spending?"*
> → calls `compare_cases` switching objective between `maxSpending` and `maxBequest`

### Strategy value and explanations

> *"How much is all this optimization actually worth compared to just spending
> taxable first and never converting?"*
> → calls `compare_to_baseline`; AI reports the extra annual and lifetime spending
> in today's dollars

> *"Why does the plan convert exactly \$48k in 2027, and what is my \$400k bequest
> goal costing me?"*
> → calls `explain_results`; AI reads the bracket-fill analysis (conversions filling
> the 12% bracket to the boundary) and the bequest-floor shadow price

---

## Notes

- **Longevity + historical:** `run_longevity_stochastic` requires `scenario_method="mc"`.
  Historical mode is rejected because random lifespans can exceed the data window.
- **Solver output** (progress, timing) goes to stderr and is never sent to the AI.
  Only the structured JSON result is returned as the tool output.
- **Long solves**: `run_case` and `compare_cases` run the LP/MIP solver in a
  background thread so the MCP event loop stays responsive. Complex cases can
  take 30 seconds to several minutes.
- **Rate method parameters**: use `list_rate_models` to find the exact parameter
  names before asking the AI to run a case with a specific rate model.
