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
| `run_case(filename, overrides, ...)` | Solve and return full JSON results | Yes |
| `compare_cases(filename, overrides, ...)` | Solve base + variant, return delta | Yes |
| `run_from_params(names, birth_years, ...)` | Build and solve from structured parameters — no TOML file needed | Yes |
| `save_case(names, birth_years, ...)` | Save structured parameters to TOML + HFP Excel for reproducibility | No |

`run_case` and `compare_cases` accept optional `solver`, `max_time`, `gap`, and `seed`
arguments. The `overrides` argument uses `KEY.PATH=VALUE` syntax identical to
`owlcli run --set` (values are JSON-parsed).

`run_from_params` and `save_case` accept the full set of plan parameters directly,
eliminating the need to write a TOML file first. All monetary balances are in $k;
time-series amounts (wages, contributions) are in $/year; Social Security in $/year
(converted to monthly PIA internally); pensions in $/month.

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

**Cursor** (`.cursor/mcp.json` or Cursor settings → MCP):
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

**Zed** (`settings.json`):
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

**Windsurf** and other Codeium-based editors: follow the same MCP stdio
configuration format as Cursor.

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
> taxable account, \$800k in a 401(k), and \$100k in a Roth IRA. I expect
> \$30k/year in Social Security at age 67. What's my optimal annual spending?"*
> → calls `run_from_params` directly — no TOML file needed

> *"Alice and Bob are both 62. Alice was born in 1963 and Bob in 1961. They
> expect to live to 90 and 87 respectively. Their combined savings are
> \$300k taxable, \$1.2M tax-deferred, and \$150k Roth. Alice will receive
> \$28k/year in SS at 67, Bob \$32k/year. Maximize their spending."*
> → calls `run_from_params` with two-person parameters

> *"Same as above but Alice earns \$90k/year until 2030, they have a \$350k
> mortgage at 3.5% with 20 years remaining, and a house worth \$800k
> (basis \$400k) they plan to sell in 2040 with 3% commission."*
> → calls `run_from_params` with `wages`, `debts`, and `fixed_assets`

> *"Save Alice and Bob's case to files so I can reload it later."*
> → calls `save_case` — writes `Case_alice+bob.toml` + `HFP_alice+bob.xlsx`

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

- **Solver output** (progress, timing) goes to stderr and is never sent to the AI.
  Only the structured JSON result is returned as the tool output.
- **Long solves**: `run_case` and `compare_cases` run the LP/MIP solver in a
  background thread so the MCP event loop stays responsive. Complex cases can
  take 30 seconds to several minutes.
- **Rate method parameters**: use `list_rate_models` to find the exact parameter
  names before asking the AI to run a case with a specific rate model.
