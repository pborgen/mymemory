"""Fixtures for the memory-agent ReAct integration test.

The suite drives the *real* LangGraph StateGraph (agent ↔ tools loop) with a
scripted chat model, so you can F5-debug the ReAct cycle without a live LLM or
a running API. Tool HTTP calls are stubbed at the httpx seam.
"""
from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr


class ScriptedChatModel(BaseChatModel):
    """Deterministic chat model that returns a fixed sequence of AIMessages.

    Unlike FakeMessagesListChatModel, this implements bind_tools so MemoryAgent
    can wire it the same way it wires a real provider model.
    """

    responses: list[AIMessage]
    _index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(
        self,
        tools: list[BaseTool],
        **kwargs: Any,
    ) -> ScriptedChatModel:
        # MemoryAgent always calls bind_tools; we ignore the schemas because
        # responses are pre-scripted with the tool_calls we want to exercise.
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self._index >= len(self.responses):
            raise RuntimeError(
                f"ScriptedChatModel exhausted after {len(self.responses)} responses; "
                "add more AIMessages to the script if the graph loops further."
            )
        message = self.responses[self._index]
        self._index += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.fixture
def remember_then_confirm() -> list[AIMessage]:
    """One ReAct turn: call remember, then confirm after the tool result."""
    return [
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
        AIMessage(content="Got it — I'll remember that your license plate is 8XYZ123."),
    ]


@pytest.fixture
def recall_then_answer() -> list[AIMessage]:
    """One ReAct turn: call recall, then answer from the tool result."""
    return [
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
