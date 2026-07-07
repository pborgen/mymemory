"""Specialist worker sub-agents for the orchestrator.

Each worker is a small, self-contained ReAct subgraph (model + tool loop) built
the same explicit way as `agents.memory.agent` — the loop stays visible. The
orchestrator graph drops these compiled subgraphs straight in as nodes, so a
worker's internal tool calls surface when the parent is streamed with
`subgraphs=True`.
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.common.model import build_chat_model


def build_worker(
    name: str,
    tools: list[BaseTool],
    system_prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
):
    """Compile a named ReAct worker bound to `tools` and `system_prompt`."""
    model = build_chat_model(temperature=temperature, max_tokens=max_tokens).bind_tools(tools)

    def call_model(state: MessagesState) -> dict:
        system = SystemMessage(content=system_prompt)
        return {"messages": [model.invoke([system, *state["messages"]])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile(name=name)
