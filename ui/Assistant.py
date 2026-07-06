"""
Embedded AI assistant page for the Owl retirement planner Streamlit UI.

Chat with an AI that can read the case currently open in the app, run the
optimizer on variants, quantify the value of strategies, and explain results
— using the same tool implementations the MCP server exposes, in-process.

Self-hosted/Docker only: the page is registered in the navigation only when
OWL_ASSISTANT=1 is set, so the hosted app never exposes it. Requires the
anthropic package and an ANTHROPIC_API_KEY (ANTHROPIC_BASE_URL is honored
for gateways and proxies).

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
import assistant_core as core
import assistant_tools as atools

st.markdown("# :material/forum: Assistant")
st.markdown("### **Owl** - *Optimal wealth lab*")
kz.divider("orange")

if not core.assistant_enabled():
    st.info(
        "The assistant is disabled. To enable it on a self-hosted or Docker installation, "
        "set `OWL_ASSISTANT=1` and `ANTHROPIC_API_KEY` in the environment and restart the app.",
        icon=":material/power_off:",
    )
    st.stop()

try:
    import anthropic
except ImportError:
    st.error(
        "The `anthropic` package is not installed. Install it with "
        "`pip install owlplanner[assistant]` (or `uv sync --extra assistant` in a checkout) "
        "and restart the app.",
        icon=":material/error:",
    )
    st.stop()


@st.cache_resource
def _client():
    return anthropic.Anthropic()


@st.cache_resource
def _tools():
    return atools.all_tool_schemas()


@st.cache_resource
def _system_prompt():
    return core.build_system_prompt()


MODEL = core.assistant_model()

st.caption(
    f"Conversations (including your case data when you ask about it) are sent to the "
    f"configured AI provider — model `{MODEL}`. The optimizer itself runs locally. "
    f"Educational and research use only; not financial, tax, or investment advice."
)

if "assistant_messages" not in st.session_state:
    st.session_state["assistant_messages"] = []  # raw API messages (incl. tool blocks)
    st.session_state["assistant_display"] = []  # [(role, text, [tool names])]

for role, text, tool_names in st.session_state["assistant_display"]:
    with st.chat_message(role):
        if tool_names:
            st.caption("Used: " + ", ".join(sorted(set(tool_names))))
        st.markdown(text)

if st.session_state["assistant_display"]:
    if st.button("Clear conversation", icon=":material/delete:"):
        st.session_state["assistant_messages"] = []
        st.session_state["assistant_display"] = []
        st.rerun()

prompt = st.chat_input(
    "Ask about your case, explore a scenario, or start a new plan…"
    if kz.has_current_case()
    else "Describe your situation to start a plan, or build a case in the app first…"
)

# Welcome screen: greeting bubble + starter prompts, only while the chat is empty.
# The greeting is display-only (the API history must start with a user message);
# a clicked starter is consumed as if the user had typed it.
if not st.session_state["assistant_display"]:
    with st.chat_message("assistant"):
        st.markdown(atools.greeting())
    starter = st.pills(
        "Suggestions",
        atools.starter_prompts(),
        key="assistant_starter",
        label_visibility="collapsed",
    )
    if starter and prompt is None:
        prompt = starter

if prompt:
    st.session_state["assistant_messages"].append({"role": "user", "content": prompt})
    st.session_state["assistant_display"].append(("user", prompt, []))
    with st.chat_message("user"):
        st.markdown(prompt)

    tools_used: list[str] = []
    with st.chat_message("assistant"):
        try:
            with st.status("Thinking…", expanded=False) as status:

                def _on_tool(name):
                    tools_used.append(name)
                    status.update(label=f"Running {name}…")
                    st.write(f"→ {name}")

                text = core.run_agent_turn(
                    _client(),
                    MODEL,
                    _system_prompt(),
                    st.session_state["assistant_messages"],
                    _tools(),
                    atools.execute_tool,
                    on_tool=_on_tool,
                )
                status.update(label="Done", state="complete")
        except anthropic.AuthenticationError:
            st.error("Invalid or missing API key — check ANTHROPIC_API_KEY.", icon=":material/key_off:")
            st.session_state["assistant_messages"].pop()
            st.session_state["assistant_display"].pop()
            st.stop()
        except anthropic.APIConnectionError:
            st.error(
                "Could not reach the AI provider — check your network or ANTHROPIC_BASE_URL.",
                icon=":material/wifi_off:",
            )
            st.session_state["assistant_messages"].pop()
            st.session_state["assistant_display"].pop()
            st.stop()
        except Exception as e:
            st.error(f"Assistant error: {e}", icon=":material/error:")
            st.session_state["assistant_messages"].pop()
            st.session_state["assistant_display"].pop()
            st.stop()

        if tools_used:
            st.caption("Used: " + ", ".join(sorted(set(tools_used))))
        st.markdown(text)

    st.session_state["assistant_display"].append(("assistant", text, tools_used))
