# Owl MCP Server — AI Integration

Owl ships with an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server
that lets any compatible AI assistant — Claude Desktop, Claude Code, Cursor, and others —
call Owl directly as a tool. The AI can discover cases, inspect configurations, run
optimizations, and compare scenarios through natural conversation.

## Tools exposed

| Tool | Description | Solves? |
|------|-------------|---------|
| `list_cases(directory)` | Enumerate `.toml` case files in a directory | No |
| `explain_case(filename, overrides)` | Describe a case: individuals, balances, income, options | No |
| `list_rate_models(category)` | Enumerate return models with parameters | No |
| `list_mortality_tables()` | Actuarial mortality tables for longevity risk sampling | No |
| `run_case(filename, overrides, ...)` | Solve and return full JSON results | Yes |
| `compare_cases(filename, overrides, ...)` | Solve base + variant, return delta | Yes |
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
directly, eliminating the need to write a TOML file first. All monetary balances
and solver limits are in full dollars ($); time-series amounts (wages, contributions)
are in $/year; Social Security is the monthly PIA from your SSA statement ($/month);
pensions are in $/month. Asset allocation arrays are `[equities, corporate_bonds,
t_notes, cash]` in percent. Fixed user rates (`rate_method="user"`) use
`[equities, corporate_bonds, t_notes, inflation]` in percent. Pre-65 ACA coverage
can be modeled via the `slcsp` parameter (annual Silver benchmark premium in $/year).

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

## Testing the server (no AI required)

FastMCP ships a browser-based inspector that lets you call tools manually
without any AI client:

```bash
uvx fastmcp dev src/owlplanner/cli/cmd_serve.py
```

This opens a local web UI where you can invoke `list_cases`, `explain_case`,
`run_case`, etc. directly. Useful for verifying the server before connecting
it to an AI.

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

> *"Robert is 69, born 1957, expects to live to 85. He has \$600k IRA,
> \$100k Roth, \$80k taxable, SS PIA \$2,400/month claiming at 68, lives
> in Ohio. He wants to keep at least \$15,000 in taxable as an emergency
> fund. Maximize his spending."*
> → calls `run_from_params` with `min_taxable_balance=[15000]`

> *"Save Alice and Bob's case to files so I can reload it later."*
> → calls `save_case` — writes `Case_alice+bob.toml` + `HFP_alice+bob.xlsx`

### Probability of success and efficient frontier

> *"What's the maximum I can spend with a 90% historical probability of success?"*
> → calls `run_stochastic` with `scenario_method="historical"`, `target_success_rate=0.90`

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
