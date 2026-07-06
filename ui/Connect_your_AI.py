"""
"Connect your AI" page for the Owl retirement planner Streamlit UI.

Generates copy-paste MCP configuration for connecting Owl's optimizer to an
AI assistant (Claude Desktop, Claude Code, Cursor, Gemini CLI, VS Code, Zed,
and other MCP-compatible clients). The MCP server runs on the user's own
computer; this page only produces the configuration.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import streamlit as st

import sskeys as kz
import connectai

st.markdown("# :material/smart_toy: Connect your AI")
st.markdown("### **Owl** - *Optimal wealth lab*")
kz.divider("orange")

st.markdown(
    """
Owl ships an **MCP server** that lets an AI assistant drive the optimizer through
natural conversation — describe your situation in plain language and the AI runs
optimizations, computes probability-of-success frontiers, quantifies the dollar value
of Roth conversion and claiming strategies, and explains *why* the plan looks the way
it does. No TOML files, no forms.

**Requirements:** Owl installed on **your own computer** (the server cannot run from
this hosted page) and an MCP-compatible AI client. Two install options:

- clone the [Owl repository](https://github.com/mdlacasse/Owl) and use
  [`uv`](https://docs.astral.sh/uv/) (recommended), or
- `pip install owlplanner`, which puts the `owlcli` command on your PATH.
"""
)

st.info(
    "**Privacy** — the Owl MCP server runs entirely on your computer and stores nothing. "
    "Your financial details are shared only with the AI assistant you choose to connect, "
    "under that provider's privacy terms.",
    icon=":material/lock:",
)

kz.divider("orange")
st.markdown("## :orange[Generate your configuration]")

col1, col2 = st.columns(2, gap="large")
with col1:
    client = st.selectbox("AI client", connectai.CLIENTS, key="connectai_client")
with col2:
    method = st.radio(
        "How is Owl installed?",
        (connectai.METHOD_UV, connectai.METHOD_PATH),
        key="connectai_method",
    )

repo_path = "/path/to/Owl"
if method == connectai.METHOD_UV:
    repo_path = st.text_input(
        "Absolute path to your Owl checkout",
        value="/path/to/Owl",
        key="connectai_path",
        help="The directory containing pyproject.toml. `uv run --project` activates the "
        "right virtual environment automatically — no PATH setup needed.",
    ).strip() or "/path/to/Owl"

setup = connectai.client_setup(client, method, repo_path)
st.markdown(setup["steps"])
st.code(setup["code"], language=setup["language"])
st.markdown(setup["after"])

kz.divider("orange")
st.markdown("## :orange[What you can ask]")
st.markdown(
    """
> *"I'm 65 with \\$800k in my IRA and \\$200k taxable, \\$2,400/month Social Security at 67 —
> what can I safely spend each year with 90% historical probability of success?"*

> *"How much is Roth conversion and withdrawal sequencing actually worth to us in dollars,
> compared to just spending taxable first and never converting?"*

> *"Why does the plan convert \\$48k in 2027 — and what is my \\$400k bequest goal costing me?"*

Clients that support MCP prompts (e.g. Claude Desktop) also expose **`owl_intake`** — a
guided interview that collects exactly the information Owl needs before the first run.
"""
)

with st.expander("What the AI can do — 16 tools"):
    st.markdown(
        """
- **Solve and iterate** — `run_from_params` builds and optimizes a plan from conversational
  input; `save_case` writes it to a case file this app can load; `compare_cases` evaluates
  what-if changes.
- **Quantify the strategy** — `compare_to_baseline` prices the optimizer's advantage against
  a conventional strategy (no conversions, stated claiming ages, taxable-first ordering) in
  today's dollars.
- **Explain the plan** — `explain_results` reports what each goal and rule costs at the
  margin (shadow prices), which tax brackets the plan fills and why, and the withdrawal
  sequencing.
- **Stress-test** — `run_historical`, `run_monte_carlo`, `run_stochastic`, and
  `run_longevity_stochastic` for backtests, Monte Carlo, spending frontiers, and longevity
  risk.
- **Reference** — rate models, mortality tables, IRS contribution limits, and Social
  Security benefit conversion.
"""
    )

if method == connectai.METHOD_UV:
    with st.expander("Test the server without an AI"):
        st.markdown("FastMCP ships a browser inspector for calling the tools manually:")
        st.code(f"uvx fastmcp dev {repo_path}/src/owlplanner/cli/cmd_serve.py", language="bash")

st.markdown(
    "Full guide with troubleshooting and more example conversations: "
    "[info/mcp.md](https://github.com/mdlacasse/Owl/blob/main/info/mcp.md)."
)

st.info(
    "Self-hosting or running the Docker image? Owl also ships a built-in **Assistant** chat "
    "page that can read the case you have open in this app. Enable it with `OWL_ASSISTANT=1` "
    "and `ANTHROPIC_API_KEY` in the environment (plus `pip install owlplanner[assistant]`).",
    icon=":material/forum:",
)
