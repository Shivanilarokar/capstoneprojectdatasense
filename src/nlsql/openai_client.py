from __future__ import annotations

from pydantic import BaseModel

from config import AppConfig

from .models import SqlGenerationResult

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in integration environments
    OpenAI = None


class _SqlGenerationPayload(BaseModel):
    reasoning: str
    tables: list[str]
    sql: str
    ambiguity: bool = False


def _get_openai_client(settings: AppConfig):
    if OpenAI is None:
        raise RuntimeError("openai is required for the NL-SQL OpenAI flow.")
    return OpenAI(api_key=settings.openai_api_key)


def generate_sql(settings: AppConfig, prompt: str) -> SqlGenerationResult:
    client = _get_openai_client(settings)
    response = client.responses.parse(
        model=settings.openai_model,
        input=[{"role": "user", "content": prompt}],
        text_format=_SqlGenerationPayload,
    )

    for output in getattr(response, "output", []):
        if getattr(output, "type", "") != "message":
            continue
        for item in getattr(output, "content", []):
            refusal = getattr(item, "refusal", None)
            if refusal:
                raise RuntimeError(f"OpenAI refused SQL generation: {refusal}")
            parsed = getattr(item, "parsed", None)
            if parsed:
                return SqlGenerationResult(
                    reasoning=parsed.reasoning,
                    tables=list(parsed.tables),
                    sql=parsed.sql,
                    ambiguity=parsed.ambiguity,
                )

    raise RuntimeError("OpenAI did not return a parseable SQL generation payload.")


def synthesize_answer(settings: AppConfig, prompt: str) -> str:
    client = _get_openai_client(settings)
    response = client.responses.create(
        model=settings.openai_model,
        input=[{"role": "user", "content": prompt}],
    )
    text = (getattr(response, "output_text", "") or "").strip()
    if text:
        return text
    raise RuntimeError("OpenAI did not return a text answer.")
