"""Integration test for the memory agent's ReAct (Reason + Act) loop.

Runs the real LangGraph graph in MemoryAgent:

    START → agent → (tools_condition) → tools → agent → … → END

A ScriptedChatModel stands in for the LLM so the suite is offline and
deterministic. Tool HTTP is stubbed at httpx.request — set a breakpoint on
call_model / ToolNode / tools_condition and F5 with the
"🧪 Agent: ReAct integration test" launch config to watch one full cycle.
"""
from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import AIMessage

from agents.memory.agent import MemoryAgent
from agents.memory import tools as memory_tools
from tests.conftest import ScriptedChatModel


def _fake_api_response(request: httpx.Request) -> httpx.Response:
    """Minimal stand-in for the MyMemory API the tools call over HTTP."""
    path = request.url.path
    if request.method == "POST" and path == "/api/memory":
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "mem-1",
                "content": body.get("content", ""),
                "source": "agent",
            },
        )
    if request.method == "POST" and path == "/api/memory/chat":
        return httpx.Response(
            200,
            json={
                "answer": "Your license plate is 8XYZ123.",
                "action": "recalled",
                "sources": [{"id": "mem-1", "content": "The user's car license plate is 8XYZ123"}],
                "sessionId": "test-session",
            },
        )
    if request.method == "GET" and path == "/api/memory":
        return httpx.Response(200, json=[])
    return httpx.Response(404, json={"error": f"unexpected {request.method} {path}"})


@pytest.fixture
def stub_http(monkeypatch):
    """Route tool HTTP through _fake_api_response (no live API required)."""

    def fake_request(method: str, url: str, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(_fake_api_response)) as client:
            return client.request(method, url, **kwargs)

    monkeypatch.setattr(memory_tools.httpx, "request", fake_request)
    # Agent construction fetches the managed prompt; keep offline.
    monkeypatch.setattr(
        "agents.memory.agent.fetch_prompt",
        lambda key, default: default,
    )


def _collect(agent: MemoryAgent, user_input: str) -> list[tuple[str, str]]:
    """Run one turn and collect (kind, text) stream events for assertions."""
    return list(agent.stream(user_input))


def test_react_remember_loops_agent_tools_agent(stub_http, remember_then_confirm):
    """Store path: model calls remember → ToolNode runs → model confirms.

    Breakpoints that teach the loop:
      - MemoryAgent._build_graph.call_model   (Reason)
      - langgraph ToolNode / tools_condition (Act + route)
      - agents.memory.tools.remember         (HTTP tool body)
    """
    model = ScriptedChatModel(responses=remember_then_confirm)
    agent = MemoryAgent(model=model)

    events = _collect(agent, "my car license plate is 8XYZ123")

    kinds = [kind for kind, _ in events]
    assert kinds == ["tool", "reply"]

    tool_event = events[0][1]
    assert tool_event.startswith("remember(")
    assert "8XYZ123" in tool_event

    assert "8XYZ123" in events[1][1]
    # Script consumed both scripted turns (tool call + final answer).
    assert model._index == 2


def test_react_recall_loops_agent_tools_agent(stub_http, recall_then_answer):
    """Recall path: model calls recall → ToolNode runs → model answers."""
    model = ScriptedChatModel(responses=recall_then_answer)
    agent = MemoryAgent(model=model)

    events = _collect(agent, "what is my license plate?")

    kinds = [kind for kind, _ in events]
    assert kinds == ["tool", "reply"]
    assert events[0][1].startswith("recall(")
    assert "8XYZ123" in events[1][1]


def test_react_multi_turn_shares_thread_checkpoint(stub_http):
    """Two turns on the same thread_id: checkpointer keeps conversation state.

    Turn 1 scripts a remember cycle; turn 2 scripts a recall cycle. Both run
    on one MemoryAgent instance so MemorySaver sees the same thread.
    """
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "remember",
                    "args": {"fact": "The user's car license plate is 8XYZ123"},
                    "id": "call_remember_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Saved your license plate."),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "recall",
                    "args": {"question": "what is my license plate?"},
                    "id": "call_recall_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Your license plate is 8XYZ123."),
    ]
    model = ScriptedChatModel(responses=responses)
    agent = MemoryAgent(model=model)

    first = _collect(agent, "my car license plate is 8XYZ123")
    second = _collect(agent, "what is my license plate?")

    assert first[0][0] == "tool" and first[0][1].startswith("remember(")
    assert second[0][0] == "tool" and second[0][1].startswith("recall(")
    assert model._index == 4
