"""
Tests for the Connect-your-AI config generation logic (ui/connectai.py).

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import json

import connectai


def test_server_command_uv():
    cmd, args = connectai.server_command(connectai.METHOD_UV, "/home/me/Owl")
    assert cmd == "uv"
    assert args == ["run", "--project", "/home/me/Owl", "owlcli", "serve"]


def test_server_command_path_install():
    cmd, args = connectai.server_command(connectai.METHOD_PATH, "/ignored")
    assert cmd == "owlcli"
    assert args == ["serve"]


def test_every_client_has_a_complete_recipe():
    for client in connectai.CLIENTS:
        for method in (connectai.METHOD_UV, connectai.METHOD_PATH):
            setup = connectai.client_setup(client, method, "/home/me/Owl")
            assert setup["steps"], client
            assert setup["code"], client
            assert setup["language"] in ("json", "bash"), client
            assert setup["after"], client


def test_json_snippets_are_valid_and_carry_the_path():
    for client in connectai.CLIENTS:
        setup = connectai.client_setup(client, connectai.METHOD_UV, "/home/me/Owl")
        if setup["language"] == "json":
            parsed = json.loads(setup["code"])  # must be valid JSON
            assert "/home/me/Owl" in setup["code"], client
            assert "serve" in setup["code"], client
            assert isinstance(parsed, dict)


def test_page_renders_and_reacts():
    """Smoke-test the page script itself via Streamlit's AppTest harness."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("ui/Connect_your_AI.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert any("Connect your AI" in str(m.value) for m in at.markdown)

    at.selectbox[0].select("Zed").run()
    assert "context_servers" in at.get("code")[0].value

    at.text_input[0].set_value("/home/me/Owl").run()
    assert "/home/me/Owl" in at.get("code")[0].value

    at.radio[0].set_value(connectai.METHOD_PATH).run()
    assert not at.exception


def test_client_specific_formats():
    path = "/home/me/Owl"
    # Zed uses the nested context_servers format.
    zed = json.loads(connectai.client_setup("Zed", connectai.METHOD_UV, path)["code"])
    assert zed["context_servers"]["owl"]["command"]["path"] == "uv"
    # VS Code Copilot uses "servers" with an explicit stdio type.
    vsc = json.loads(connectai.client_setup("VS Code (GitHub Copilot)", connectai.METHOD_UV, path)["code"])
    assert vsc["servers"]["owl"]["type"] == "stdio"
    # Claude Desktop / Cursor / Gemini use mcpServers.
    cd = json.loads(connectai.client_setup("Claude Desktop", connectai.METHOD_UV, path)["code"])
    assert cd["mcpServers"]["owl"]["command"] == "uv"
    # Claude Code is a shell one-liner.
    cc = connectai.client_setup("Claude Code (CLI)", connectai.METHOD_PATH, path)
    assert cc["language"] == "bash"
    assert cc["code"] == "claude mcp add owl -- owlcli serve"
