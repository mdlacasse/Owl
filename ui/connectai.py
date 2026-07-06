"""
Config-generation logic for the "Connect your AI" page.

Pure functions (no Streamlit imports) that build the MCP server launch command
and per-client configuration snippets shown on the Connect_your_AI page.
Kept separate from the page script so they can be unit-tested.

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

import json

CLIENTS = (
    "Claude Desktop",
    "Claude Code (CLI)",
    "Cursor",
    "Gemini CLI",
    "VS Code (GitHub Copilot)",
    "VS Code (Cline)",
    "Zed",
    "Windsurf / other MCP client",
)

METHOD_UV = "uv checkout of the Owl repository (recommended)"
METHOD_PATH = "owlcli on PATH (pip or pipx install owlplanner)"


def server_command(method, repo_path):
    """Return (command, args) launching the Owl MCP server for the chosen install method."""
    if method == METHOD_UV:
        return "uv", ["run", "--project", repo_path, "owlcli", "serve"]
    return "owlcli", ["serve"]


def _mcp_servers_json(cmd, args):
    return json.dumps({"mcpServers": {"owl": {"command": cmd, "args": args}}}, indent=2)


def client_setup(client, method, repo_path):
    """
    Return the setup recipe for one client as a dict:
      {"steps": markdown, "code": snippet, "language": "json"|"bash", "after": markdown}
    """
    cmd, args = server_command(method, repo_path)
    servers_json = _mcp_servers_json(cmd, args)
    shell_cmd = " ".join([cmd] + args)

    if client == "Claude Desktop":
        return {
            "steps": (
                "Edit Claude Desktop's MCP configuration file:\n"
                "- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`\n"
                "- **Windows**: `%APPDATA%\\Claude\\claude_desktop_config.json`\n\n"
                "Add (or merge) this entry:"
            ),
            "code": servers_json,
            "language": "json",
            "after": "Restart Claude Desktop. The Owl tools and the `owl_intake` prompt appear automatically.",
        }
    if client == "Claude Code (CLI)":
        return {
            "steps": "Register the server with one command:",
            "code": f"claude mcp add owl -- {shell_cmd}",
            "language": "bash",
            "after": "Verify with `claude mcp list`. Claude Code starts the server on demand.",
        }
    if client == "Cursor":
        return {
            "steps": (
                "Either **Cursor Settings → MCP → Add new MCP server** (name it `owl`, "
                f"command `{cmd}`, args `{' '.join(args)}`), or create/edit "
                "`~/.cursor/mcp.json` (user-wide; use `.cursor/mcp.json` in a project "
                "for a project-only setup):"
            ),
            "code": servers_json,
            "language": "json",
            "after": (
                "Confirm the server shows **Connected** in Settings → MCP, then ask a "
                "retirement question in **Agent** chat."
            ),
        }
    if client == "Gemini CLI":
        return {
            "steps": (
                "Add the server to `~/.gemini/settings.json` (user-wide) or "
                "`.gemini/settings.json` at a project root:"
            ),
            "code": servers_json,
            "language": "json",
            "after": "Restart Gemini CLI; inspect registered servers with the `/mcp` command.",
        }
    if client == "VS Code (GitHub Copilot)":
        return {
            "steps": (
                "Requires VS Code 1.99+ with Copilot Chat in agent mode. Create "
                "`.vscode/mcp.json` in your workspace (or add under the `\"mcp\"` key "
                "in user `settings.json`):"
            ),
            "code": json.dumps(
                {"servers": {"owl": {"type": "stdio", "command": cmd, "args": args}}}, indent=2
            ),
            "language": "json",
            "after": "Open Copilot Chat, switch to **Agent** mode, and type `#owl` or describe your scenario.",
        }
    if client == "VS Code (Cline)":
        return {
            "steps": (
                "Open the Cline panel → **MCP Servers** icon → **Edit MCP Settings**, "
                "and add the `owl` entry:"
            ),
            "code": servers_json,
            "language": "json",
            "after": "The tools become available immediately — no restart required.",
        }
    if client == "Zed":
        return {
            "steps": "Edit `~/.config/zed/settings.json`:",
            "code": json.dumps(
                {"context_servers": {"owl": {"command": {"path": cmd, "args": args}}}}, indent=2
            ),
            "language": "json",
            "after": "Restart Zed after saving.",
        }
    # Windsurf and any other stdio MCP client follow the mcpServers pattern.
    return {
        "steps": (
            "Any client that supports the MCP stdio transport uses the same pattern — "
            "a command and argument list that launches `owlcli serve`. Most use the "
            "`mcpServers` format:"
        ),
        "code": servers_json,
        "language": "json",
        "after": "Consult your client's documentation for the configuration file location.",
    }
