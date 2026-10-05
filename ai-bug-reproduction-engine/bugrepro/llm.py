"""Optional Anthropic client with a safe no-key fallback."""

from __future__ import annotations

import json
import re
from typing import Any

from bugrepro.config import Settings


class LLMError(RuntimeError):
    """Raised when the remote model cannot be used."""


def _strip_fence(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:python|json)?\n([\s\S]*?)\n```$", text)
    return match.group(1) if match else text


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = bool(settings.anthropic_api_key)

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        if not self.enabled:
            raise LLMError("ANTHROPIC_API_KEY is not set; using offline heuristics.")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError("anthropic package is not installed") from exc

        client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        kwargs: dict[str, Any] = {
            "model": self.settings.anthropic_model,
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        message = client.messages.create(**kwargs)
        parts = [block.text for block in message.content if getattr(block, "type", "") == "text"]
        text = _strip_fence("\n".join(parts))
        if json_mode:
            json.loads(text)  # validate
        return text
