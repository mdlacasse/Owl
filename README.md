<!--
Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
SPDX-License-Identifier: CC-BY-NC-SA-4.0
This documentation is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0; see LICENSE-docs in the repository root.
-->

# Owl - Optimal wealth lab

[![CI](https://github.com/mdlacasse/owl/actions/workflows/github-actions-runtests.yml/badge.svg?branch=main)](https://github.com/mdlacasse/owl/actions/workflows/github-actions-runtests.yml?query=branch%3Amain)
[![Version](https://img.shields.io/badge/dynamic/regex?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmdlacasse%2Fowl%2Fmain%2Fsrc%2Fowlplanner%2Fversion.py&search=__version__%20%3D%20%22(%5B%5E%22%5D%2B)%22&replace=%241&label=latest)](https://github.com/mdlacasse/owl/blob/main/src/owlplanner/version.py)
[![PyPI](https://img.shields.io/pypi/v/owlplanner)](https://pypi.org/project/owlplanner/)
[![Python](https://img.shields.io/pypi/pyversions/owlplanner)](https://pypi.org/project/owlplanner/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Docker](https://img.shields.io/docker/v/owlplanner/owldocker?label=docker&cacheSeconds=86400)](https://hub.docker.com/r/owlplanner/owldocker)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://owlplanner.streamlit.app)

## Open-source retirement planning optimizer powered by Actual Intelligence — connect it to your AI assistant

*Roth conversion optimizer · Social Security claiming strategy · Monte Carlo retirement simulator · Python retirement calculator · AI retirement planner · MCP retirement tool · Claude Gemini Cursor Zed VS Code*

---

<img align="right" src="https://raw.githubusercontent.com/mdlacasse/Owl/main/assets/owl.png" width="350">


### TL;DR
Owl is an open-source **retirement planning tool** that helps US retirees answer the hardest
questions in retirement income planning: when to claim Social Security, how much to convert
to Roth each year, which accounts to withdraw from first, and how to minimize lifetime taxes.
It uses mixed-integer linear programming to *optimize* withdrawal strategies rather than
merely simulate them, finding the mathematically best sequence of decisions across all
accounts simultaneously.

Users can stress-test their plan with historical back-testing, Monte Carlo simulation
with sequence-of-returns risk, or fixed rates derived from historical averages.

Owl covers the full US tax landscape: federal income tax, state income taxes for all
50 states and DC, long-term capital gains, NIIT, Medicare IRMAA surcharges, ACA marketplace
premiums, RMDs, and Roth conversion rules — all embedded directly in the optimizer so that
tax-efficient retirement income planning is built into every result, not applied as an afterthought.

<p align="center">
<img src="https://raw.githubusercontent.com/mdlacasse/Owl/main/info/images/chris+pat_savings.png" width="700" alt="Owl Savings Balance plot: tax-deferred accounts drawn down while Roth balances grow through optimized conversions">
<br>
<em>Optimized account balances over time (today's dollars): Owl draws down tax-deferred
accounts while growing tax-free Roth balances through early-retirement conversions.</em>
</p>

-------------------------------------------------------------------------------------

## Key capabilities

- **Tax optimization** — federal + state income tax (all 50 states + DC), LTCG brackets, NIIT, Medicare IRMAA, and ACA premiums all embedded in the optimizer
- **Account types** — taxable, tax-deferred (401k/IRA), Roth, and HSA accounts with full contribution and withdrawal rules
- **Roth conversions** — amounts and timing co-optimized with spending and bequest goals
- **Value of optimization** — `compare_to_baseline` solves the same plan with and without the strategy (no Roth conversions, Social Security at stated ages, taxable-first withdrawal ordering) and reports the advantage in today's dollars — a mathematical lower bound from the optimizer itself, not a simulation estimate
- **Explainability** — `explain_results` reads the LP shadow prices to report what each goal and rule costs at the margin, which tax brackets the plan deliberately fills (and why), and the order in which accounts are drawn down. Every recommendation is explained using the mathematics of the optimization itself: the AI interprets and narrates quantities computed by the solver — it does not find the answer
- **Social Security** — own, spousal, and survivor benefits; optional MILP co-optimization of claiming age (monthly resolution, 62–70)
- **Pension & SPIA** — pension income with survivor fractions; IRA-funded SPIA with optional CPI indexing and joint-and-survivor benefit
- **Two objectives** — maximize net spending subject to a bequest floor, or maximize after-tax bequest subject to a spending floor
- **Spending profile** — flat or smile-curve shape with survivorship factor; optional time-preference discounting to reduce end-of-life back-loading
- **Asset allocation** — user-specified glide path (linear or s-curve) across four asset classes (equities, corporate bonds, T-notes, cash); per-account, per-individual, or household-wide
- **Stochastic analysis** — Monte Carlo with optional longevity risk (mortality tables by sex and category: SSA, VBT, RP-2014, IAM-2012, Pub-2010); spending efficiency frontier tracing the optimal spending vs. shortfall-risk trade-off
- **Rate models** — 14 models including historical replay, bootstrap, VAR, GARCH-DCC, HMM, GMM, and Gaussian copula
- **AI assistant** — MCP server lets Claude Desktop, Claude Code, Gemini CLI, Cursor, Zed, VS Code (Copilot/Cline), and other MCP-compatible AI clients run optimizations, compute probability-of-success frontiers, quantify and explain strategies, and compare scenarios through natural conversation — sixteen tools plus a guided `owl_intake` interview prompt, with every assumption made for omitted inputs disclosed in the response (`assumed_defaults`). No TOML files required:
  > *"I'm 65, have $800k in my IRA and $200k taxable, $2,400/month Social Security at 67 — what can I safely spend each year with 90% historical probability of success?"*

  Self-hosted installs can also enable a built-in **Assistant** chat page that reads the case open in the app (`OWL_ASSISTANT=1`); the **Connect your AI** page in the web UI generates the client configuration either way.

Among open-source retirement planning tools, Owl stands out for the breadth and rigor of its financial modeling. While the full API rewards those willing to invest time, the Streamlit web interface provides an accessible entry point for all users.


## How to run Owl

There are four ways to run Owl (from easiest to more complex):

1) **Streamlit Hub:** Run Owl remotely as hosted on the Streamlit Community Cloud at
[owlplanner.streamlit.app](https://owlplanner.streamlit.app).

1) **Docker Container:** Run Owl locally on your computer using a Docker image.
Follow these <a href="https://github.com/mdlacasse/Owl/blob/main/docker/README.md" target="_blank" rel="noopener noreferrer">instructions</a> for using this option.

1) **Self-hosting:** Run Owl locally on your computer using Python code and libraries.
Follow these <a href="https://github.com/mdlacasse/Owl/blob/main/INSTALL.md" target="_blank" rel="noopener noreferrer">instructions</a> to install from the source code and self-host on your own computer.

1) **AI assistant (MCP):** Connect Owl as a tool to an AI assistant — Claude Desktop,
Claude Code, Gemini CLI, Cursor, Zed, VS Code (Copilot or Cline), or any
[MCP-compatible client](https://modelcontextprotocol.io).
The AI can discover cases, run optimizations, compute probability-of-success frontiers,
and compare scenarios through natural conversation — no TOML files required.
Requires a local installation; see <a href="https://github.com/mdlacasse/Owl/blob/main/info/mcp.md" target="_blank" rel="noopener noreferrer">info/mcp.md</a> for setup.
The *Connect your AI* page (under Tools in the web UI) generates the copy-paste
configuration for Claude Desktop, Claude Code, Cursor, Gemini CLI, VS Code, and Zed.


## Documentation

| Document | Description |
|---------|-------------|
| 📥 <a href="https://github.com/mdlacasse/Owl/blob/main/INSTALL.md" target="_blank" rel="noopener noreferrer">Installation Guide</a> | Installation, Python environment setup, and developer build steps |
| 📋 <a href="https://github.com/mdlacasse/Owl/blob/main/CHANGELOG.md" target="_blank" rel="noopener noreferrer">Changelog</a> | Version history and changelog |
| 🤝 <a href="https://github.com/mdlacasse/Owl/blob/main/CONTRIBUTING.md" target="_blank" rel="noopener noreferrer">Contributing</a> | Guidelines for contributing code, issues, and pull requests |
| 📊 <a href="https://github.com/mdlacasse/Owl/blob/main/info/modeling-capabilities.md" target="_blank" rel="noopener noreferrer">Modeling Capabilities</a> | Summary of modeled components, assumptions, and limitations |
| 📖 <a href="https://github.com/mdlacasse/Owl/blob/main/info/USER_GUIDE.md" target="_blank" rel="noopener noreferrer">User Guide</a> | Python API usage with examples for Jupyter notebooks and scripts |
| ⚙️ <a href="https://github.com/mdlacasse/Owl/blob/main/info/PARAMETERS.md" target="_blank" rel="noopener noreferrer">Parameter Reference</a> | Complete reference for TOML case file parameters |
| 📈 <a href="https://github.com/mdlacasse/Owl/blob/main/info/RATE_MODELS.md" target="_blank" rel="noopener noreferrer">Rate Models</a> | Available rate models (historical, stochastic, bootstrap, etc.) |
| 🤖 <a href="https://github.com/mdlacasse/Owl/blob/main/info/mcp.md" target="_blank" rel="noopener noreferrer">MCP Server</a> | MCP server setup for AI-native access via Claude, Gemini, Cursor, Zed, VS Code, and other clients |
| 🖥️ <a href="https://owlplanner.streamlit.app/Documentation" target="_blank" rel="noopener noreferrer">Web App Guide</a> | Guide to the Streamlit web app user interface |
| 📐 <a href="https://github.com/mdlacasse/Owl/blob/main/papers/owl.pdf" target="_blank" rel="noopener noreferrer">Mathematical Foundations</a> | The LP formulation paper (owl.pdf) |


## Credits and Acknowledgements
See <a href="https://github.com/mdlacasse/Owl/blob/main/CREDITS.md" target="_blank" rel="noopener noreferrer">CREDITS.md</a>.

## Bugs and Feature Requests
Please submit bugs and feature requests through
[GitHub](https://github.com/mdlacasse/owl/issues) if you have a GitHub account
or directly by [email](mailto:martin.d.lacasse@gmail.com).
Or just drop me a line to report your experience with the tool.

## Privacy
This app does not store or forward any information. All data entered is lost
after a session is closed. However, you can choose to download selected parts of your
own data to your computer before closing the session. These data will be stored strictly on
your computer and can be used to reproduce a case at a later time.

The optional self-hosted **Assistant** page is disabled by default and never available
on the hosted app; when you explicitly enable it, your conversation — including case
data you ask about — is sent to the AI provider you configure. The optimizer itself
always runs locally.


## Licensing

Copyright &copy; 2024-2026 Martin-D. Lacasse and The Owl Authors.

This project is distributed under three separate licenses depending on the type of file:

- **Source code** (`.py`, `.sh`) is licensed under the
  **GNU General Public License v3** (see [LICENSE](https://github.com/mdlacasse/Owl/blob/main/LICENSE)).
- **Documentation** (`.md`, `.qmd`, `.ipynb`, `.tex`) is licensed under the
  **Creative Commons Attribution-NonCommercial-ShareAlike 4.0** license, CC-BY-NC-SA-4.0
  (see [LICENSE-docs](https://github.com/mdlacasse/Owl/blob/main/LICENSE-docs)).
- **Name, logo, and image assets** — the **Owl - Optimal wealth lab** name and the
  logo/icon image files in the `assets/` directory — are **all rights reserved**,
  Copyright &copy; 2024-2026 Martin-D. Lacasse. They are **not** covered by the GPLv3 and
  may not be reproduced or modified without permission (see [assets/LICENSE](https://github.com/mdlacasse/Owl/blob/main/assets/LICENSE)).


## Disclaimers

**Owl** is for **educational and research purposes** only. Nothing in this session constitutes **financial, tax, or
investment advice**—consult a qualified professional for decisions specific to your situation.

Code output has been verified with analytical solutions when applicable, and comparative approaches otherwise.
Nevertheless, accuracy of results is not guaranteed.

