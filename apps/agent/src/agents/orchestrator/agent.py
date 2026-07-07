"""Supervisor multi-agent system for the memory app.

A single orchestrator graph coordinates four specialists:

    route (supervisor)  classifies the turn → store | recall | chat
      ├─ store  → Archivist   (writer worker: splits & saves facts)
      ├─ recall → Retriever   (reader worker: answers from saved memories)
      │             → Verifier (critic: is the answer grounded? retry if not)
      └─ chat   → small talk   (direct reply, no tools)

The Archivist and Retriever are compiled ReAct subgraphs (see `workers.py`)
added straight in as nodes; the Verifier is a structured-output critic that can
bounce an ungrounded answer back to the Retriever once before giving up.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel, Field

from agents.common.model import build_chat_model
from agents.common.prompts import fetch_prompt
from agents.memory.tools import USER_EMAIL, list_all_memories, recall, remember
from agents.orchestrator.workers import build_worker

MAX_ATTEMPTS = 2  # one retry: Retriever answers, Verifier may bounce it back once.

ROUTER_PROMPT = """You are the supervisor of a personal-memory assistant team.
Classify the user's latest message into exactly one destination:
- store: the user is telling you one or more facts about themselves to remember.
- recall: the user is asking about something they told you earlier.
- chat: greetings, small talk, or questions about how you work — not facts.
Choose the single best destination."""

ARCHIVIST_PROMPT = """You are the Archivist. You persist facts the user shares.
For each DISTINCT fact in the user's message, call `remember` once with a clean,
self-contained statement — resolve pronouns and context (e.g. "The user's car
license plate is 8XYZ123"). Split compound statements into separate `remember`
calls. After saving, briefly confirm what you stored. Never invent facts."""

RETRIEVER_PROMPT = """You are the Retriever. Answer the user's question using
ONLY their saved memories. Call `recall` to look something up, or
`list_all_memories` to browse. Base your answer strictly on what the tools
return; if nothing relevant is saved, say so honestly. Be concise and natural."""

VERIFIER_PROMPT = """You are the Verifier, a strict fact-checker on the team.
Given the EVIDENCE (the retriever's tool output / the user's saved memories) and
a PROPOSED ANSWER, decide whether the answer is fully supported by the evidence.
Set grounded=false if the answer adds, guesses at, or contradicts anything not
present in the evidence. "I don't have that saved" is a grounded answer when the
evidence is empty. Give brief, actionable feedback."""

CHAT_PROMPT = """You are a friendly personal-memory assistant for {email}. The
user is making small talk or asking how you work. Reply briefly, and remind them
they can tell you facts to remember or ask you to recall them."""


class _Route(BaseModel):
    destination: Literal["store", "recall", "chat"] = Field(
        description="Where to send the user's latest message."
    )


class _Verdict(BaseModel):
    grounded: bool = Field(description="True if the answer is fully supported by the evidence.")
    feedback: str = Field(description="Brief note on what is unsupported, if anything.")


class OrchestratorState(MessagesState):
    route: str
    attempts: int
    verdict: str


def _last_ai_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = message.content if isinstance(message.content, str) else str(message.content)
            if text.strip():
                return text
    return ""


def _tool_evidence(messages: list) -> str:
    chunks = [str(m.content) for m in messages if isinstance(m, ToolMessage)]
    return "\n---\n".join(chunks) if chunks else "(no memories retrieved)"


class OrchestratorAgent:
    """Supervisor agent coordinating archivist / retriever / verifier workers."""

    def __init__(self) -> None:
        # Resolve managed prompts from the API once at construction; the module
        # constants are the offline fallback if the API is unreachable.
        self._router_prompt = fetch_prompt("orchestrator.router", ROUTER_PROMPT)
        self._verifier_prompt = fetch_prompt("orchestrator.verifier", VERIFIER_PROMPT)
        self._chat_prompt = fetch_prompt("orchestrator.chat", CHAT_PROMPT)
        archivist_prompt = fetch_prompt("orchestrator.archivist", ARCHIVIST_PROMPT)
        retriever_prompt = fetch_prompt("orchestrator.retriever", RETRIEVER_PROMPT)

        self._router = build_chat_model(temperature=0.0, max_tokens=256).with_structured_output(
            _Route
        )
        self._verifier = build_chat_model(temperature=0.0, max_tokens=512).with_structured_output(
            _Verdict
        )
        self._chat = build_chat_model(temperature=0.3, max_tokens=512)
        self._archivist = build_worker("archivist", [remember], archivist_prompt)
        self._retriever = build_worker("retriever", [recall, list_all_memories], retriever_prompt)
        self._graph = self._build_graph()
        self._thread_id = str(uuid.uuid4())

    def _build_graph(self):
        def route(state: OrchestratorState) -> dict:
            decision = self._router.invoke(
                [SystemMessage(content=self._router_prompt), *state["messages"]]
            )
            return {"route": decision.destination}

        def smalltalk(state: OrchestratorState) -> dict:
            system = SystemMessage(content=self._chat_prompt.format(email=USER_EMAIL))
            return {"messages": [self._chat.invoke([system, *state["messages"]])]}

        def verify(state: OrchestratorState) -> dict:
            attempts = state.get("attempts", 0) + 1
            draft = _last_ai_text(state["messages"])
            evidence = _tool_evidence(state["messages"])
            verdict = self._verifier.invoke(
                [
                    SystemMessage(content=self._verifier_prompt),
                    HumanMessage(
                        content=(
                            f"EVIDENCE (saved memories / recall output):\n{evidence}\n\n"
                            f"PROPOSED ANSWER:\n{draft}\n\n"
                            "Is the proposed answer fully supported by the evidence?"
                        )
                    ),
                ]
            )
            out: dict = {
                "attempts": attempts,
                "verdict": "grounded" if verdict.grounded else f"ungrounded: {verdict.feedback}",
            }
            if not verdict.grounded and attempts < MAX_ATTEMPTS:
                out["messages"] = [
                    HumanMessage(
                        content=(
                            "[verifier] Your previous answer was not grounded: "
                            f"{verdict.feedback} Re-check the saved memories and answer "
                            "again, using ONLY what is actually saved."
                        )
                    )
                ]
            return out

        def pick_worker(state: OrchestratorState) -> str:
            return {"store": "archivist", "recall": "retriever", "chat": "smalltalk"}[state["route"]]

        def after_verify(state: OrchestratorState) -> str:
            if state.get("verdict", "").startswith("ungrounded") and state.get("attempts", 0) < MAX_ATTEMPTS:
                return "retry"
            return "done"

        graph = StateGraph(OrchestratorState)
        graph.add_node("route", route)
        graph.add_node("archivist", self._archivist)
        graph.add_node("retriever", self._retriever)
        graph.add_node("verify", verify)
        graph.add_node("smalltalk", smalltalk)

        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route",
            pick_worker,
            {"archivist": "archivist", "retriever": "retriever", "smalltalk": "smalltalk"},
        )
        graph.add_edge("archivist", END)
        graph.add_edge("smalltalk", END)
        graph.add_edge("retriever", "verify")
        graph.add_conditional_edges("verify", after_verify, {"retry": "retriever", "done": END})
        return graph.compile(checkpointer=MemorySaver())

    def stream(self, user_input: str) -> Iterator[tuple[str, str]]:
        """Run one turn, yielding events:
        ("route", dest) | ("agent", label) | ("tool", "label: call") |
        ("verify", verdict) | ("reply", text).
        """
        config = {"configurable": {"thread_id": self._thread_id}}
        initial = {"messages": [("human", user_input)], "attempts": 0}
        active: str | None = None

        for namespace, update in self._graph.stream(
            initial, config, stream_mode="updates", subgraphs=True
        ):
            in_worker = bool(namespace)
            label = namespace[-1].split(":")[0] if in_worker else None

            for node, node_output in update.items():
                if not isinstance(node_output, dict):
                    continue

                # Supervisor-level signals.
                if not in_worker and node == "route":
                    yield ("route", node_output.get("route", "?"))
                    continue
                if not in_worker and node == "verify":
                    yield ("verify", node_output.get("verdict", "?"))
                    continue

                # Reply from the small-talk node (no worker, no tools).
                if not in_worker and node == "smalltalk":
                    text = _last_ai_text(node_output.get("messages", []))
                    if text:
                        yield ("reply", text)
                    continue

                # Skip the parent-level echo of a finished worker; we stream the
                # worker's own internal updates (in_worker) instead.
                if not in_worker:
                    continue

                if label and label != active:
                    active = label
                    yield ("agent", label)

                for message in node_output.get("messages", []):
                    if isinstance(message, AIMessage) and message.tool_calls:
                        for call in message.tool_calls:
                            args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
                            yield ("tool", f"{label}: {call['name']}({args})")
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
