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

`run_case` and `compare_cases` accept optional `solver`, `max_time`, `gap`, and `seed`
arguments. The `overrides` argument uses `KEY.PATH=VALUE` syntax identical to
`owlcli run --set` (values are JSON-parsed).

---

## Starting the server

```bash
owlcli serve
```

The server communicates over stdio — no port, no network. Each AI client starts
it as a subprocess; you do not run it manually.

---

## Claude Desktop

Add Owl to Claude Desktop's MCP server list by editing
`claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### If `owlcli` is on your PATH

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

### If `owlcli` lives in a project virtual environment

Use the full path to the venv's binary:

```json
{
  "mcpServers": {
    "owl": {
      "command": "/path/to/Owl/.venv/bin/owlcli",
      "args": ["serve"]
    }
  }
}
```

Or, if you manage the project with `uv`:

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

Restart Claude Desktop after saving. The tools appear automatically in the
conversation interface.

---

## Claude Code (CLI)

Add Owl as an MCP server in the current project:

```bash
claude mcp add owl owlcli serve
```

Or, for a project venv:

```bash
claude mcp add owl /path/to/Owl/.venv/bin/owlcli serve
```

Claude Code will start `owlcli serve` automatically when the MCP server is needed.

---

## Other MCP-compatible clients

Any client that supports the MCP stdio transport uses the same pattern —
a command and argument list that starts `owlcli serve`. Common examples:

**Cursor** (`.cursor/mcp.json` or Cursor settings → MCP):
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

**Zed** (`settings.json`):
```json
{
  "context_servers": {
    "owl": {
      "command": {
        "path": "owlcli",
        "args": ["serve"]
      }
    }
  }
}
```

**Windsurf** and other Codeium-based editors: follow the same MCP stdio
configuration format as Cursor.

---

## Example interactions

Once connected, you can ask the AI naturally:

> *"What cases are in my examples folder?"*
> → calls `list_cases("examples/")`

> *"Describe the jack+jill case."*
> → calls `explain_case("examples/Case_jack+jill.toml")`

> *"What stochastic rate models are available?"*
> → calls `list_rate_models("stochastic")`

> *"Run the jack+jill case and tell me the optimal spending."*
> → calls `run_case("examples/Case_jack+jill.toml")`

> *"How much does moving to Minnesota change their spending?"*
> → calls `compare_cases("examples/Case_jack+jill.toml", ["basic_info.state=MN"])`

> *"Compare delaying both SS claims to age 70 vs. the current plan."*
> → calls `compare_cases(..., ["fixed_income.social_security_ages=[70,70]"])`

---

## Notes

- **Solver output** (progress, timing) goes to stderr and is never sent to the AI.
  Only the structured JSON result is returned as the tool output.
- **Long solves**: `run_case` and `compare_cases` run the LP/MIP solver in a
  background thread so the MCP event loop stays responsive. Complex cases can
  take 30 seconds to several minutes.
- **Rate method parameters**: use `list_rate_models` to find the exact parameter
  names before asking the AI to run a case with a specific rate model.
