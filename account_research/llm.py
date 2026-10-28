"""Model clients. The pipeline depends only on the small LLM protocol, so the
Anthropic client can be swapped for any other provider or a scripted fake."""
from __future__ import annotations

import json
import os
import re
from typing import Protocol

DEFAULT_MODEL = os.environ.get("ACCOUNT_RESEARCH_MODEL", "claude-sonnet-5-5")


class LLM(Protocol):
    name: str

    def complete(self, system: str, messages: list[dict]) -> str:
        """messages is a list of {"role": "user" | "assistant", "content": str}."""


class AnthropicLLM:
    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 3000):
        import anthropic  # imported lazily so tests don't need an API key

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Set ANTHROPIC_API_KEY to run live research (or use --fixtures with --scripted).")
        self.client = anthropic.Anthropic()
        self.name = model
        self.max_tokens = max_tokens

    def complete(self, system: str, messages: list[dict]) -> str:
        resp = self.client.messages.create(
            model=self.name, max_tokens=self.max_tokens, system=system, messages=messages
        )
        return "".join(block.text for block in resp.content if block.type == "text")


class ScriptedLLM:
    """Returns pre-written replies in order. Used by tests and offline demos."""

    def __init__(self, replies: list[str], name: str = "scripted"):
        self.replies = list(replies)
        self.name = name
        self.calls: list[tuple[str, list[dict]]] = []

    def complete(self, system: str, messages: list[dict]) -> str:
        self.calls.append((system, messages))
        if not self.replies:
            raise RuntimeError("ScriptedLLM ran out of replies")
        return self.replies.pop(0)


def parse_json_reply(text: str) -> dict:
    """Pull the JSON object out of a reply, tolerating ```json fences or stray prose."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in the reply")
    return json.loads(cleaned[start:end + 1])
