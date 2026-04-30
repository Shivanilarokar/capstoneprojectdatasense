"""OpenAI LLM helper utilities with retry/backoff for production resilience."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Dict

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError


def _parse_json_object(text: str) -> Dict:
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


def _call_with_backoff(
    *,
    client: OpenAI,
    model: str,
    prompt: str,
    temperature: float,
    max_retries: int,
    initial_backoff_sec: float,
) -> str:
    request_client = client.with_options(max_retries=max_retries, timeout=30.0)
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = request_client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()
        except (RateLimitError, APIConnectionError) as exc:
            last_error = exc
        except APIStatusError as exc:
            last_error = exc
            if exc.status_code not in {408, 409, 429} and (exc.status_code or 0) < 500:
                raise
        if attempt == max_retries - 1 and last_error is not None:
            raise last_error
        time.sleep(initial_backoff_sec * (2**attempt))
    return ""


def chat_text(
    client: OpenAI,
    model: str,
    prompt: str,
    temperature: float = 0,
    max_retries: int = 4,
    initial_backoff_sec: float = 1.0,
) -> str:
    """Call chat completions with retry/backoff and return text content."""
    return _call_with_backoff(
        client=client,
        model=model,
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
    if not (getattr(client, "api_key", None) or os.getenv("OPENAI_API_KEY", "").strip()):
        raise RuntimeError("OPENAI_API_KEY is required for LLM generation.")
    parsed = _parse_json_object(
        _call_with_backoff(
            client=client,
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_retries=max_retries,
            initial_backoff_sec=1.0,
        )
    )
    return parsed if isinstance(parsed, dict) else {}


