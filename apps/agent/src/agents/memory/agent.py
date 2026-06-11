"""LangGraph tool-using memory agent.

Explicit StateGraph so the agent loop is visible: the model decides whether to
call a tool (remember / recall / list), the tool node executes it, and control
loops back until the model produces a final answer. Conversation memory is
handled by a checkpointer keyed on a thread id.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.common.model import build_chat_model
from agents.memory.tools import MEMORY_TOOLS, USER_EMAIL

SYSTEM_PROMPT = """You are a personal memory assistant for {email}.

The user either tells you something to remember about their life, or asks you to \
recall something they told you earlier.

- When they state a fact, call `remember` with a clean, self-contained statement \
capturing it, then briefly confirm what you saved.
- When they ask a question, call `recall` to look it up, then answer using only \
what comes back. If nothing relevant is saved, say so honestly.
- Use the tools — never guess or invent the user's information.
Be concise and natural."""


class MemoryAgent:
    def __init__(self) -> None:
        model = build_chat_model(temperature=0.2, max_tokens=1024)
        self._model = model.bind_tools(MEMORY_TOOLS)
        self._graph = self._build_graph()
        self._thread_id = str(uuid.uuid4())

    def _build_graph(self):
        def call_model(state: MessagesState) -> dict:
            system = SystemMessage(content=SYSTEM_PROMPT.format(email=USER_EMAIL))
            response = self._model.invoke([system, *state["messages"]])
            return {"messages": [response]}

        graph = StateGraph(MessagesState)
        graph.add_node("agent", call_model)
        graph.add_node("tools", ToolNode(MEMORY_TOOLS))
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=MemorySaver())

    def stream(self, user_input: str) -> Iterator[tuple[str, str]]:
        """Run one turn, yielding ("tool", description) and ("reply", text) events."""
        config = {"configurable": {"thread_id": self._thread_id}}
        for update in self._graph.stream(
            {"messages": [("human", user_input)]}, config, stream_mode="updates"
        ):
            for node_output in update.values():
                for message in node_output.get("messages", []):
                    if isinstance(message, AIMessage) and message.tool_calls:
                        for call in message.tool_calls:
                            args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
                            yield ("tool", f"{call['name']}({args})")
                    elif isinstance(message, ToolMessage):
                        continue
                    elif isinstance(message, AIMessage):
                        text = (
                            message.content
                            if isinstance(message.content, str)
                            else str(message.content)
                        )
                        if text.strip():
                            yield ("reply", text)

    def reset(self) -> None:
        self._thread_id = str(uuid.uuid4())
