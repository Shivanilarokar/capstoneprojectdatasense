"""Corrective query rewriting for weak orchestrator retrieval passes."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.generation.generation import LLMConfig, chat_text
from .state import GraphState


def _clean_question(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip("?!.")


def _failed_context_summary(state: GraphState) -> str:
    route_results = state.get("route_results", {}) or {}
    if not route_results:
        return "No route outputs were produced."

    summaries: list[str] = []
    for route, result in route_results.items():
        answer_preview = str(result.get("answer", "")).strip().replace("\n", " ")[:300]
        evidence_preview = json.dumps(result.get("evidence", {}), ensure_ascii=False)[:400]
        summaries.append(
            f"[{route}] Answer preview: {answer_preview or 'none'}\n"
            f"[{route}] Evidence preview: {evidence_preview or 'none'}"
        )
    return "\n\n".join(summaries)


def _fallback_rewrite(question: str, state: GraphState) -> str:
    selected_pipeline = str(state.get("selected_pipeline", "")).strip().lower()
    suffix_map = {
        "pageindex": "latest SEC filing disclosure and 10-K narrative",
        "sanctions": "OFAC or BIS sanctions screening evidence",
        "nlsql": "exact database records, rows, and tabular metrics",
        "graphrag": "supplier dependency, downstream exposure, and cascade graph evidence",
        "fullstack": "cross-source evidence from filings, structured analytics, sanctions, and graph exposure",
    }
    suffix = suffix_map.get(selected_pipeline, "the most specific matching evidence")
    return f"{_clean_question(question)} Focus on {suffix}."


def rewrite_query(state: GraphState) -> dict[str, Any]:
    """Rewrite the active retrieval query after weak route grading."""
    question = state["question"]
    previous_query = state.get("effective_question") or question
    failed_context = _failed_context_summary(state)
    llm = None
    if state["settings"].openai_api_key:
        llm = LLMConfig(api_key=state["settings"].openai_api_key, model=state["settings"].openai_model)

    if llm is None:
        rewritten = _fallback_rewrite(previous_query, state)
    else:
        prompt = f"""
You are rewriting a supply-chain user query to improve retrieval in a multi-route orchestrator.

Reason silently before answering. Do not reveal chain-of-thought.

Original user question:
{question}

Current retrieval query:
{previous_query}

Weak or misaligned route outputs:
{failed_context}

Rewrite the query so it is:
- more specific
- better aligned to likely document or database vocabulary
- still faithful to the user's original meaning
- concise enough to use directly for retrieval

Do not answer the question.
Return only the rewritten retrieval query.
""".strip()
        rewritten = chat_text(llm, prompt, temperature=0).strip()

    cleaned_rewrite = _clean_question(rewritten)
    rewrite_applied = bool(cleaned_rewrite) and cleaned_rewrite.lower() != _clean_question(previous_query).lower()
    return {
        "retrieval_query": previous_query,
        "rewritten_question": cleaned_rewrite if rewrite_applied else state.get("rewritten_question", ""),
        "effective_question": cleaned_rewrite if rewrite_applied else previous_query,
        "rewrite_applied": rewrite_applied,
    }
