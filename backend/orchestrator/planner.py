"""Route planner for the live LangGraph orchestrator."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.generation.generation import LLMConfig, chat_json

RouteHint = Literal["pageindex", "sanctions", "nlsql", "graphrag"]
PipelineHint = Literal["pageindex", "sanctions", "nlsql", "graphrag", "fullstack"]
TierHint = Literal["tier_0", "tier_1", "tier_2"]

PAGEINDEX_HINT_RE = re.compile(
    r"(?i)\b(10-k|10-q|item\s*1a|item\s*7a?|md&a|risk factors?|sec filing|annual filing|disclose[sd]?)\b"
)
SANCTIONS_HINT_RE = re.compile(r"(?i)\b(sanction\w*|ofac|bis|entity list|screen)\b")
NLSQL_HINT_RE = re.compile(
    r"(?i)\b(noaa|fda|warning letter|import alert|comtrade|trade flow|top\s+\d+|highest|how many|count|storm damage|exports?|imports?|states?|countries?)\b"
)
GRAPHRAG_HINT_RE = re.compile(r"(?i)\b(cascade|tier\s*[234]|downstream|graph|dependency|multi-tier|hazard exposure)\b")

COMPARISON_PATTERNS = [
    re.compile(r"\bcompare\b", re.IGNORECASE),
    re.compile(r"\bvs\.?\b", re.IGNORECASE),
    re.compile(r"\bcontradict", re.IGNORECASE),
    re.compile(r"\bdifference between\b", re.IGNORECASE),
]

GRAPH_ROUTE_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bcascade|downstream|dependency|tier\s*[234]|multi-tier\b"), "cascade"),
    (re.compile(r"(?i)\bsanction\w*|ofac|entity list\b"), "sanctions"),
    (re.compile(r"(?i)\btrade flow|export|import|comtrade\b"), "trade"),
    (re.compile(r"(?i)\bhazard|storm damage|weather\b"), "hazard"),
    (re.compile(r"(?i)\bfda|warning letter|import alert|regulator|regulatory\b"), "regulatory"),
    (re.compile(r"(?i)\brevenue|financial|exposure\b"), "financial"),
)


class PlannedSubquestion(BaseModel):
    question: str = Field(description="A standalone sub-question.")
    route_hint: RouteHint | None = Field(default=None, description="Preferred route for the sub-question.")


class QueryPlan(BaseModel):
    plan_type: Literal["single", "multi"] = Field(description="Whether the query stays whole or decomposes.")
    reason: str = Field(description="Short reason for the decision.")
    tier_hint: TierHint = Field(description="Expected execution tier.")
    pipeline: PipelineHint = Field(description="Primary execution pipeline.")
    routes: list[RouteHint] = Field(description="Concrete routes to execute.")
    graph_routes: list[str] = Field(default_factory=list, description="Optional graph sub-routes.")
    confidence: float = Field(description="Planner confidence from 0 to 1.")
    planner: Literal["heuristic", "llm"] = Field(description="Which planner produced the output.")
    subquestions: list[PlannedSubquestion] = Field(description="Sub-questions to execute or keep together.")


def _model_validate(model: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    validator = getattr(model, "model_validate", None)
    if callable(validator):
        return validator(payload)
    return model.parse_obj(payload)


def _clean_question(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip("?!.")


def _extract_route_hits(question: str) -> list[RouteHint]:
    hits: list[RouteHint] = []
    for route, matcher in (
        ("pageindex", PAGEINDEX_HINT_RE),
        ("sanctions", SANCTIONS_HINT_RE),
        ("nlsql", NLSQL_HINT_RE),
        ("graphrag", GRAPHRAG_HINT_RE),
    ):
        if matcher.search(question):
            hits.append(route)
    return hits


def _graph_routes_for_question(question: str) -> list[str]:
    selected: list[str] = []
    for pattern, route in GRAPH_ROUTE_HINTS:
        if pattern.search(question) and route not in selected:
            selected.append(route)
    return selected


def _guess_route_hint(question: str) -> RouteHint:
    hits = _extract_route_hits(question)
    return hits[0] if hits else "nlsql"


def _canonical_tier(plan_type: str, routes: list[str]) -> TierHint:
    if plan_type == "multi" or len(routes) > 1:
        return "tier_2"
    if routes and routes[0] in {"pageindex", "graphrag"}:
        return "tier_1"
    return "tier_0"


def _normalize_subquestions(subquestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for subquestion in subquestions:
        cleaned = _clean_question(str(subquestion.get("question", "")))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        route_hint = subquestion.get("route_hint") or _guess_route_hint(cleaned)
        normalized.append({"question": cleaned, "route_hint": route_hint})
    return normalized


def _single_plan(question: str, route: RouteHint, reason: str, *, planner_name: str = "heuristic") -> dict[str, Any]:
    subquestions = [{"question": question, "route_hint": route}]
    return {
        "plan_type": "single",
        "pipeline": route,
        "routes": [route],
        "graph_routes": _graph_routes_for_question(question) if route == "graphrag" else [],
        "confidence": 0.7 if planner_name == "heuristic" else 0.9,
        "reason": reason,
        "planner": planner_name,
        "tier_hint": _canonical_tier("single", [route]),
        "subquestions": _normalize_subquestions(subquestions),
    }


def _multi_plan(question: str, routes: list[RouteHint], reason: str, *, planner_name: str = "heuristic") -> dict[str, Any]:
    subquestion_templates = {
        "pageindex": "What do the relevant SEC filing disclosures say about this issue?",
        "sanctions": "Is there sanctions or entity-list exposure for the target company?",
        "nlsql": "What exact database evidence, counts, or tabular records answer this question?",
        "graphrag": "What downstream dependency, cascade, or graph exposure follows from this issue?",
    }
    subquestions = [
        {"question": subquestion_templates.get(route, question), "route_hint": route}
        for route in routes
    ]
    return {
        "plan_type": "multi",
        "pipeline": "fullstack",
        "routes": routes,
        "graph_routes": _graph_routes_for_question(question),
        "confidence": 0.6 if planner_name == "heuristic" else 0.9,
        "reason": reason,
        "planner": planner_name,
        "tier_hint": "tier_2",
        "subquestions": _normalize_subquestions(subquestions),
    }


def should_decompose(question: str) -> bool:
    hits = _extract_route_hits(question)
    if len(hits) > 1:
        return True
    return any(pattern.search(question) for pattern in COMPARISON_PATTERNS) and len(hits) >= 1


def _fallback_plan_query(question: str) -> dict[str, Any]:
    clean_question = _clean_question(question)
    hits = _extract_route_hits(clean_question)
    if not hits:
        return _multi_plan(
            clean_question,
            ["nlsql", "graphrag"],
            "No single evidence source dominates, so use structured analytics plus graph reasoning.",
        )
    if len(hits) == 1 and not should_decompose(clean_question):
        return _single_plan(
            clean_question,
            hits[0],
            f"The question is best served by the `{hits[0]}` route.",
        )
    return _multi_plan(
        clean_question,
        hits,
        "The question spans multiple evidence modes and needs orchestrated fusion.",
    )


def _llm_plan(question: str, llm: LLMConfig, pageindex_tickers: list[str] | None = None) -> dict[str, Any]:
    prompt = f"""
You are the senior planning step for a supply-chain intelligence LangGraph system.

Reason silently before answering. Do not reveal chain-of-thought.
Return only strict JSON.

You must choose one pipeline:
- pageindex: SEC 10-K / 10-Q / disclosure narrative retrieval
- sanctions: deterministic OFAC / BIS screening
- nlsql: exact analytics over NOAA / FDA / Comtrade / regulatory tables
- graphrag: supplier dependency, cascade, and graph exposure reasoning
- fullstack: combine multiple routes and synthesize

Current PageIndex SEC coverage tickers:
{pageindex_tickers or []}

Guidance:
- Keep queries `single` unless they clearly span multiple evidence pools.
- Use `multi` for questions that combine sanctions + analytics + graph exposure, or filing analysis + another evidence mode.
- Do not split on the word "and" by itself.
- Prefer the smallest route set that fully answers the question.
- `tier_hint` must be `tier_0`, `tier_1`, or `tier_2`.

Return JSON with this exact shape:
{{
  "plan_type": "single|multi",
  "reason": "short explanation",
  "tier_hint": "tier_0|tier_1|tier_2",
  "pipeline": "pageindex|sanctions|nlsql|graphrag|fullstack",
  "routes": ["pageindex"],
  "graph_routes": ["cascade"],
  "confidence": 0.0,
  "planner": "llm",
  "subquestions": [
    {{"question": "standalone sub-question", "route_hint": "nlsql"}}
  ]
}}

Question:
{question}
""".strip()
    parsed = chat_json(llm, prompt, temperature=0)
    parsed["planner"] = "llm"
    validated = _model_validate(QueryPlan, parsed)
    payload = validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
    payload["subquestions"] = _normalize_subquestions(payload.get("subquestions", []))
    payload["routes"] = [route for route in payload.get("routes", []) if route in {"pageindex", "sanctions", "nlsql", "graphrag"}]
    payload["graph_routes"] = [route for route in payload.get("graph_routes", []) if route in {"financial", "sanctions", "trade", "hazard", "regulatory", "cascade"}]
    return payload


def plan_query(
    question: str,
    *,
    llm: LLMConfig | None = None,
    pageindex_tickers: list[str] | None = None,
) -> dict[str, Any]:
    """Plan the live route execution strategy for a user question."""
    clean_question = _clean_question(question)
    heuristic_plan = _fallback_plan_query(clean_question)
    if llm is None:
        return heuristic_plan

    try:
        llm_plan = _llm_plan(clean_question, llm, pageindex_tickers=pageindex_tickers)
    except Exception:
        return heuristic_plan

    if not llm_plan.get("routes"):
        return heuristic_plan
    if llm_plan.get("plan_type") == "single" and len(llm_plan["routes"]) != 1:
        return heuristic_plan
    if llm_plan.get("pipeline") != "fullstack" and llm_plan["routes"][0] != llm_plan.get("pipeline"):
        return heuristic_plan
    return llm_plan
