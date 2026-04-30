"""Corrective and self-RAG grading for the live orchestrator."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.generation.generation import LLMConfig, chat_text
from .state import GraphState


class BinaryGrade(BaseModel):
    score: Literal["yes", "no"] = Field(description="Binary grading decision.")


def _parse_binary_grade(text: str) -> Literal["yes", "no"]:
    lowered = (text or "").strip().lower()
    if lowered.startswith("yes"):
        return "yes"
    return "no"


def _llm_for_state(state: GraphState) -> LLMConfig | None:
    settings = state["settings"]
    if not settings.openai_api_key:
        return None
    return LLMConfig(api_key=settings.openai_api_key, model=settings.openai_model)


def _format_route_result(route: str, result: dict[str, Any]) -> str:
    answer = str(result.get("answer", "")).strip()
    evidence = json.dumps(result.get("evidence", {}), ensure_ascii=False)[:1200]
    provenance = json.dumps(result.get("provenance", {}), ensure_ascii=False)[:600]
    return (
        f"Route: {route}\n"
        f"Answer: {answer}\n"
        f"Evidence: {evidence}\n"
        f"Provenance: {provenance}"
    )


def _format_context_for_grading(state: GraphState) -> str:
    route_results = state.get("filtered_route_results") or state.get("route_results") or {}
    if not route_results:
        return ""
    return "\n\n".join(_format_route_result(route, result) for route, result in route_results.items())


def _heuristic_route_grade(result: dict[str, Any]) -> Literal["yes", "no"]:
    answer = str(result.get("answer", "")).strip().lower()
    if not answer or "route failed:" in answer:
        return "no"
    if result.get("evidence") or result.get("provenance"):
        return "yes"
    return "no"


def _binary_grade(llm: LLMConfig | None, prompt: str) -> Literal["yes", "no"]:
    if llm is None:
        return "no"
    return _parse_binary_grade(chat_text(llm, prompt, temperature=0))


def grade_route_results(state: GraphState) -> dict[str, Any]:
    """Grade route outputs for relevance before evidence validation."""
    route_results = state.get("route_results", {})
    planned_routes = state.get("planned_routes", [])
    if not route_results:
        return {
            "filtered_route_results": {},
            "route_relevance": [],
            "doc_relevance": [],
            "relevant_route_count": 0,
            "relevant_doc_count": 0,
            "rewrite_recommended": False,
            "rewrite_reason": "No route outputs were available to grade.",
        }

    llm = _llm_for_state(state)
    question = state.get("effective_question") or state["question"]

    filtered_route_results: dict[str, dict[str, Any]] = {}
    route_relevance: list[str] = []
    for route, result in route_results.items():
        if llm is None:
            score = _heuristic_route_grade(result)
        else:
            prompt = f"""
You are grading whether a route result is relevant to a user's supply-chain question.

Reason silently before answering. Do not reveal chain-of-thought.
Return only:
yes
or
no

Question:
{question}

Route output:
{_format_route_result(route, result)}

Rules:
- yes: contains useful evidence or a materially useful partial answer
- no: irrelevant, empty, too generic, or clearly failed
""".strip()
            score = _binary_grade(llm, prompt)

        route_relevance.append(score)
        if score == "yes":
            filtered_route_results[route] = result

    target_answers = max(1, min(2, len(planned_routes))) if state.get("selected_pipeline") == "fullstack" else 1
    relevant_route_count = len(filtered_route_results)
    rewrite_recommended = relevant_route_count < target_answers
    if rewrite_recommended:
        rewrite_reason = "The first pass did not produce enough relevant route evidence."
    else:
        rewrite_reason = ""

    return {
        "filtered_route_results": filtered_route_results,
        "route_relevance": route_relevance,
        "doc_relevance": route_relevance,
        "relevant_route_count": relevant_route_count,
        "relevant_doc_count": relevant_route_count,
        "rewrite_recommended": rewrite_recommended,
        "rewrite_reason": rewrite_reason,
    }


def grade_hallucination(state: GraphState) -> dict[str, Any]:
    """Check whether the generated answer is grounded in route context."""
    answer = str(state.get("answer", "")).strip()
    context = _format_context_for_grading(state)
    if not answer or not context:
        return {"hallucination_grade": "no"}

    llm = _llm_for_state(state)
    if llm is None:
        return {"hallucination_grade": "yes"}

    prompt = f"""
You are checking whether a final answer is grounded in the available route context.

Reason silently before answering. Do not reveal chain-of-thought.
Return only:
yes
or
no

Context:
{context}

Answer:
{answer}
""".strip()
    return {"hallucination_grade": _binary_grade(llm, prompt)}


def grade_answer_quality(state: GraphState) -> dict[str, Any]:
    """Check whether the generated answer actually addresses the user question."""
    answer = str(state.get("answer", "")).strip()
    question = state["question"]
    if not answer:
        return {"answer_quality_grade": "no"}

    llm = _llm_for_state(state)
    if llm is None:
        return {"answer_quality_grade": "yes"}

    prompt = f"""
You are checking whether a final answer is useful and responsive to the user.

Reason silently before answering. Do not reveal chain-of-thought.
Return only:
yes
or
no

Question:
{question}

Answer:
{answer}
""".strip()
    return {"answer_quality_grade": _binary_grade(llm, prompt)}
