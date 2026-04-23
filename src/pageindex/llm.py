"""OpenAI LLM helper utilities with retry/backoff for production resilience."""

from __future__ import annotations

import os
from typing import Dict

from openai import OpenAI

from generation.generation import LLMConfig, chat_json as shared_chat_json, chat_text as shared_chat_text


def _resolve_api_key(client: OpenAI) -> str:
    """Extract api key from OpenAI client or fallback to env."""
    key = getattr(client, "api_key", None)
    if isinstance(key, str) and key.strip():
        return key.strip()
    return os.getenv("OPENAI_API_KEY", "").strip()


def chat_text(
    client: OpenAI,
    model: str,
    prompt: str,
    temperature: float = 0,
    max_retries: int = 4,
    initial_backoff_sec: float = 1.0,
) -> str:
    """Call chat completions with retry/backoff and return text content."""
    llm = LLMConfig(api_key=_resolve_api_key(client), model=model)
    return shared_chat_text(
        llm=llm,
        prompt=prompt,
        temperature=temperature,
        max_retries=max_retries,
        initial_backoff_sec=initial_backoff_sec,
    )


def chat_json(
    client: OpenAI,
    model: str,
    prompt: str,
    temperature: float = 0,
    max_retries: int = 4,
) -> Dict:
    """Call chat and parse JSON object with retry/backoff and tolerant parsing."""
    llm = LLMConfig(api_key=_resolve_api_key(client), model=model)
    parsed = shared_chat_json(
        llm=llm,
        prompt=prompt,
        temperature=temperature,
        max_retries=max_retries,
    )
    return parsed if isinstance(parsed, dict) else {}
