"""Centralized LLM generation helpers for all pipelines."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class LLMConfig:
    """Simple runtime config for OpenAI generation."""

    api_key: str
    model: str


def _parse_json_object(text: str) -> dict[str, Any]:
    payload = (text or "").strip()
    try:
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    block = re.search(r"\{[\s\S]*\}", payload)
    if not block:
        return {}
    try:
        parsed = json.loads(block.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def chat_text(
    llm: LLMConfig,
    prompt: str,
    *,
    temperature: float = 0.0,
    max_retries: int = 4,
    initial_backoff_sec: float = 1.0,
) -> str:
    """Generate text via OpenAI chat completions with retry/backoff."""
    if not llm.api_key:
        raise RuntimeError("OPENAI_API_KEY is required for LLM generation.")

    client = OpenAI(api_key=llm.api_key)
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=llm.model,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_retries - 1:
                raise
            time.sleep(initial_backoff_sec * (2**attempt))
    if last_error:
        raise last_error
    return ""


def chat_json(
    llm: LLMConfig,
    prompt: str,
    *,
    temperature: float = 0.0,
    max_retries: int = 4,
) -> dict[str, Any]:
    """Generate and parse JSON object with tolerant parsing."""
    text = chat_text(llm, prompt, temperature=temperature, max_retries=max_retries)
    return _parse_json_object(text)

