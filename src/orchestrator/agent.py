"""LangGraph-native competition orchestrator for route-specific and fullstack execution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from Generation.generation import LLMConfig, chat_json, chat_text
from config import AppConfig

from .contracts import make_result_envelope, normalize_graphrag_result, normalize_nlsql_result, normalize_pageindex_result
from .models import OrchestratorState
from .tools import build_route_tools


@dataclass(frozen=True)
class AgenticOptions:
    """Runtime knobs for central routing/execution."""

    force_pipeline: str | None = None
    use_llm_synthesis: bool = True
    graph_max_results: int = 20

    pageindex_sections_json: Path = Path("data/ingestion/sec/extracted_10k_sections.json")
    pageindex_docs_dir: Path = Path("src/pageindex/pageindex_docs")
    pageindex_workspace: Path = Path("src/pageindex/pageindex_workspace")
    pageindex_output_dir: Path = Path("src/pageindex/pageindex_rag_output")

    pageindex_openai_model: str | None = None
    pageindex_index_model: str | None = None
    pageindex_retrieve_model: str | None = None
    pageindex_reindex: bool = False
    pageindex_max_context_chars: int = 30000
    pageindex_index_mode: str = "md"
    pageindex_max_docs: int = 2
    pageindex_max_depth: int = 4
    pageindex_max_nodes_per_level: int = 3
    pageindex_max_candidate_nodes: int = 20

AgentState = OrchestratorState


PIPELINE_OPTIONS = ["pageindex", "sanctions", "nlsql", "graphrag", "fullstack"]
MAX_FULLSTACK_ROUTE_CALLS = 4
GRAPH_ALLOWED_ROUTES = ["financial", "sanctions", "trade", "hazard", "regulatory", "cascade"]

PAGEINDEX_HINT_RE = re.compile(
    r"(?i)\b(10-k|item\s*1a|item\s*7a?|md&a|risk factors?|sec filing|disclose[sd]?|annual filing)\b"
)
SANCTIONS_HINT_RE = re.compile(r"(?i)\b(sanction\w*|ofac|bis|entity list|screen)\b")
NLSQL_HINT_RE = re.compile(
    r"(?i)\b(noaa|fda|warning letter|import alert|comtrade|trade flow|top\s+\d+|highest|how many|count|storm damage|exports?|imports?|states?|countries?)\b"
)
GRAPHRAG_HINT_RE = re.compile(r"(?i)\b(cascade|tier\s*[234]|downstream|graph|dependency|multi-tier|hazard exposure)\b")


def _normalize_pipeline(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    return value if value in PIPELINE_OPTIONS else "fullstack"


def _normalize_routes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    selected: list[str] = []
    for item in raw:
        route = str(item).strip().lower()
        if route in GRAPH_ALLOWED_ROUTES and route not in selected:
            selected.append(route)
    return selected


def _resolve_path(project_root: Path, value: Path) -> Path:
    if value.is_absolute():
        return value
    return (project_root / value).resolve()


def _load_pageindex_tickers(sections_json_path: Path) -> list[str]:
    if not sections_json_path.exists():
        return []
    try:
        rows = json.loads(sections_json_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(rows, list):
        return []
    tickers: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker", "")).strip().upper()
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


def _heuristic_plan(question: str) -> dict[str, Any]:
    pageindex_hit = bool(PAGEINDEX_HINT_RE.search(question))
    sanctions_hit = bool(SANCTIONS_HINT_RE.search(question))
    nlsql_hit = bool(NLSQL_HINT_RE.search(question))
    graphrag_hit = bool(GRAPHRAG_HINT_RE.search(question))

    routes = [
        route
        for route, hit in (
            ("pageindex", pageindex_hit),
            ("sanctions", sanctions_hit),
            ("nlsql", nlsql_hit),
            ("graphrag", graphrag_hit),
        )
        if hit
    ]
    if not routes:
        pipeline = "fullstack"
        routes = ["nlsql", "graphrag"]
        reason = "No single route dominates; use structured analytics plus graph reasoning."
    elif len(routes) == 1:
        pipeline = routes[0]
        reason = f"Question is best served by the `{pipeline}` route."
    else:
        pipeline = "fullstack"
        reason = "Question spans multiple evidence modes and needs orchestrated fusion."
    return {
        "pipeline": pipeline,
        "routes": routes,
        "graph_routes": ["cascade"] if graphrag_hit and "cascade" in question.lower() else [],
        "confidence": 0.55,
        "reason": reason,
        "planner": "heuristic",
    }


def _llm_plan(question: str, llm: LLMConfig, pageindex_tickers: list[str]) -> dict[str, Any]:
    prompt = f"""
You are the top-level router for a supply-chain intelligence platform.

You must choose exactly one pipeline mode:
- pageindex: SEC 10-K narrative extraction/tree search
- sanctions: deterministic OFAC/BIS entity screening
- nlsql: PostgreSQL analytics over sanctions/trade/hazard/regulatory tables
- graphrag: graph analytics across sanctions/trade/hazard/regulatory/cascade
- fullstack: combine multiple routes and fuse outputs

Current PageIndex SEC coverage tickers:
{pageindex_tickers}

GraphRAG capabilities:
{GRAPH_ALLOWED_ROUTES}

Routing guidance:
1) Pure SEC filing language/disclosure comparison -> pageindex
2) Pure sanctions screening/entity-list matching -> sanctions
3) Pure exact analytics over NOAA/FDA/Comtrade/OFAC tables -> nlsql
4) Graph-native tier/cascade/dependency questions -> graphrag
5) Multi-source or multi-route questions -> fullstack

Return strict JSON:
{{
  "pipeline": "pageindex|sanctions|nlsql|graphrag|fullstack",
  "routes": ["sanctions", "nlsql"],
  "graph_routes": ["financial", "sanctions"],
  "confidence": 0.0,
  "reason": "short explanation"
}}

Question:
{question}
"""
    parsed = chat_json(llm, prompt, temperature=0)
    routes = parsed.get("routes", [])
    if not isinstance(routes, list):
        routes = []
    normalized_routes = [
        route for route in (_normalize_pipeline(str(item)) for item in routes) if route in PIPELINE_OPTIONS[:-1]
    ]
    return {
        "pipeline": _normalize_pipeline(str(parsed.get("pipeline", ""))),
        "routes": normalized_routes,
        "graph_routes": _normalize_routes(parsed.get("graph_routes", [])),
        "confidence": float(parsed.get("confidence", 0.0)) if str(parsed.get("confidence", "")).strip() else 0.0,
        "reason": str(parsed.get("reason", "")).strip() or "No reason provided.",
        "planner": "llm",
    }


def _run_pageindex_query(
    settings: AppConfig,
    question: str,
    options: AgenticOptions,
) -> dict[str, Any]:
    from pageindex.pipeline import run_pipeline as run_pageindex_pipeline

    sections_json = _resolve_path(settings.project_root, options.pageindex_sections_json)
    docs_dir = _resolve_path(settings.project_root, options.pageindex_docs_dir)
    workspace = _resolve_path(settings.project_root, options.pageindex_workspace)
    output_dir = _resolve_path(settings.project_root, options.pageindex_output_dir)

    summary = run_pageindex_pipeline(
        sections_json_path=sections_json,
        docs_dir=docs_dir,
        workspace=workspace,
        output_dir=output_dir,
        question=question,
        openai_model=options.pageindex_openai_model or settings.openai_model,
        index_model=options.pageindex_index_model,
        retrieve_model=options.pageindex_retrieve_model,
        reindex=options.pageindex_reindex,
        docs_only=False,
        max_context_chars=options.pageindex_max_context_chars,
        index_mode=options.pageindex_index_mode,
        max_docs=options.pageindex_max_docs,
        max_depth=options.pageindex_max_depth,
        max_nodes_per_level=options.pageindex_max_nodes_per_level,
        max_candidate_nodes=options.pageindex_max_candidate_nodes,
    )

    qa_result: dict[str, Any] | None = None
    qa_path_raw = summary.get("qa_result_file")
    if qa_path_raw:
        qa_path = Path(str(qa_path_raw))
        if qa_path.exists():
            try:
                qa_loaded = json.loads(qa_path.read_text(encoding="utf-8"))
                if isinstance(qa_loaded, dict):
                    qa_result = qa_loaded
            except Exception:  # noqa: BLE001
                qa_result = None

    return {
        "status": "ok",
        "summary": summary,
        "qa_result": qa_result,
        "answer": (qa_result or {}).get("answer", ""),
    }


def _run_pageindex_route(settings: AppConfig, question: str, options: AgenticOptions) -> dict[str, Any]:
    return normalize_pageindex_result(
        question,
        settings.graph_tenant_id,
        _run_pageindex_query(settings, question, options),
    )


def _run_sanctions_route(settings: AppConfig, question: str, user_id: str) -> dict[str, Any]:
    from sanctions.query import run_sanctions_query

    return run_sanctions_query(settings, question, user_id=user_id)


def _run_nlsql_route(settings: AppConfig, question: str) -> dict[str, Any]:
    from nlsql.query import run_nlsql_query

    return normalize_nlsql_result(
        question,
        settings.graph_tenant_id,
        run_nlsql_query(settings, question),
    )


def _run_graphrag_route(
    settings: AppConfig,
    question: str,
    options: AgenticOptions,
    *,
    user_id: str,
    graph_routes_hint: list[str] | None = None,
) -> dict[str, Any]:
    from graphrag.query import run_graph_query

    return normalize_graphrag_result(
        question,
        settings.graph_tenant_id,
        run_graph_query(
            settings=settings,
            question=question,
            max_results=options.graph_max_results,
            use_llm_synthesis=options.use_llm_synthesis,
            user_id=user_id,
            forced_routes=graph_routes_hint or [],
        ),
    )


def _fallback_fullstack_answer(question: str, route_results: dict[str, dict[str, Any]]) -> str:
    parts = [f"Question: {question}"]
    for route in route_results:
        parts.append(f"{route}: {route_results[route].get('answer', '')}")
    return "\n".join(parts)


def _synthesize_fullstack_answer(
    question: str,
    route_results: dict[str, dict[str, Any]],
    llm: LLMConfig,
) -> str:
    prompt = f"""
You are the final answer synthesizer for a supply-chain agentic system.
Merge route outputs into one concise answer. Use sanctions and numeric facts as anchors.
If evidence is missing, explicitly disclose that gap. Preserve trade freshness caveats.

Question:
{question}

Route outputs:
{json.dumps(route_results, ensure_ascii=False)[:70000]}
"""
    return chat_text(llm, prompt, temperature=0)


def _finalize_result(
    *,
    question: str,
    settings: AppConfig,
    selected_pipeline: str,
    route_plan: dict[str, Any],
    route_results: dict[str, dict[str, Any]],
    options: AgenticOptions,
) -> dict[str, Any]:
    routes_executed = list(route_results.keys())
    planned_routes = list(route_plan.get("planned_routes") or route_plan.get("routes") or routes_executed)
    if selected_pipeline == "fullstack":
        warnings = [warning for result in route_results.values() for warning in result.get("warnings", [])]
        freshness = {route: result.get("freshness", {}) for route, result in route_results.items()}
        provenance = {route: result.get("provenance", {}) for route, result in route_results.items()}
        if settings.openai_api_key and options.use_llm_synthesis:
            llm = LLMConfig(api_key=settings.openai_api_key, model=settings.openai_model)
            try:
                answer = _synthesize_fullstack_answer(question, route_results, llm)
            except Exception:
                answer = _fallback_fullstack_answer(question, route_results)
        else:
            answer = _fallback_fullstack_answer(question, route_results)
        envelope = make_result_envelope(
            question=question,
            route="fullstack",
            answer=answer,
            evidence={route: result.get("evidence", {}) for route, result in route_results.items()},
            provenance=provenance,
            freshness=freshness,
            warnings=warnings,
            debug={"route_plan": route_plan},
            tenant_id=settings.graph_tenant_id,
        )
    else:
        only_result = route_results[routes_executed[0]]
        envelope = dict(only_result)

    envelope.update(
        {
            "question": question,
            "tenant_id": settings.graph_tenant_id,
            "selected_pipeline": selected_pipeline,
            "route_plan": route_plan,
            "planned_routes": planned_routes,
            "completed_routes": routes_executed,
            "routes_executed": routes_executed,
            "route_results": route_results,
        }
    )
    return envelope


def _bounded_routes(routes: list[str]) -> list[str]:
    bounded: list[str] = []
    for route in routes:
        normalized = _normalize_pipeline(route)
        if normalized in PIPELINE_OPTIONS[:-1] and normalized not in bounded:
            bounded.append(normalized)
        if len(bounded) >= MAX_FULLSTACK_ROUTE_CALLS:
            break
    return bounded


def _run_tool_for_route(
    *,
    route: str,
    question: str,
    state: AgentState,
) -> dict[str, Any]:
    settings = state["settings"]
    options = state["options"]
    tools = build_route_tools(settings, user_id=state["user_id"], options=options)
    tool = tools[route]
    payload: dict[str, Any] = {"question": question}
    if route == "graphrag":
        payload["graph_routes_hint"] = state.get("graph_routes_hint", [])
    try:
        return tool.invoke(payload)
    except Exception as exc:  # noqa: BLE001
        return make_result_envelope(
            question=question,
            route=route,
            answer=f"{route} route failed: {exc}",
            warnings=[str(exc)],
            debug={"tool_error": repr(exc)},
            tenant_id=settings.graph_tenant_id,
        )


def _route_question_node(state: AgentState) -> dict[str, Any]:
    settings = state["settings"]
    question = state["question"]
    options = state["options"]

    llm = LLMConfig(api_key=settings.openai_api_key, model=settings.openai_model)
    sections_json = _resolve_path(settings.project_root, options.pageindex_sections_json)
    pageindex_tickers = _load_pageindex_tickers(sections_json)
    forced = _normalize_pipeline(options.force_pipeline) if options.force_pipeline else ""
    if forced:
        route_plan = {
            "pipeline": forced,
            "routes": _heuristic_plan(question)["routes"] if forced == "fullstack" else [forced],
            "graph_routes": [],
            "confidence": 1.0,
            "reason": "Pipeline forced by caller override.",
            "planner": "forced",
        }
    elif settings.openai_api_key:
        try:
            route_plan = _llm_plan(question, llm, pageindex_tickers=pageindex_tickers)
            if route_plan["pipeline"] == "fullstack" and not route_plan.get("routes"):
                route_plan["routes"] = _heuristic_plan(question)["routes"]
        except Exception:
            route_plan = _heuristic_plan(question)
    else:
        route_plan = _heuristic_plan(question)

    selected_pipeline = route_plan["pipeline"]
    graph_routes_hint = _normalize_routes(route_plan.get("graph_routes", []))
    pending_routes = route_plan.get("routes", [])
    if selected_pipeline != "fullstack":
        pending_routes = [selected_pipeline]
    elif not pending_routes:
        pending_routes = _heuristic_plan(question)["routes"]

    bounded = _bounded_routes(pending_routes)
    route_plan = dict(route_plan)
    planned_routes = bounded if selected_pipeline == "fullstack" else [selected_pipeline]
    route_plan["routes"] = planned_routes
    route_plan["planned_routes"] = planned_routes
    route_plan["tool_budget"] = MAX_FULLSTACK_ROUTE_CALLS if selected_pipeline == "fullstack" else 1
    if selected_pipeline == "fullstack" and len(bounded) < len(pending_routes):
        route_plan["budget_limited"] = True

    return {
        "route_plan": route_plan,
        "selected_pipeline": selected_pipeline,
        "graph_routes_hint": graph_routes_hint,
        "pending_routes": bounded,
        "planned_routes": planned_routes,
        "route_results": {},
        "completed_routes": [],
        "routes_executed": [],
    }


def _route_mode(state: AgentState) -> Literal["run_single_route", "plan_fullstack"]:
    return "plan_fullstack" if state["selected_pipeline"] == "fullstack" else "run_single_route"


def _run_single_route_node(state: AgentState) -> dict[str, Any]:
    route = state["selected_pipeline"]
    result = _run_tool_for_route(route=route, question=state["question"], state=state)
    return {
        "route_results": {route: result},
        "completed_routes": [route],
        "routes_executed": [route],
        "pending_routes": [],
    }


def _plan_fullstack_node(state: AgentState) -> dict[str, Any]:
    planned_routes = _bounded_routes(state.get("pending_routes", []))
    route_plan = dict(state["route_plan"])
    route_plan["routes"] = planned_routes
    route_plan["planned_routes"] = planned_routes
    return {
        "pending_routes": planned_routes,
        "planned_routes": planned_routes,
        "route_plan": route_plan,
    }


def _run_next_fullstack_route_node(state: AgentState) -> dict[str, Any]:
    pending_routes = list(state.get("pending_routes", []))
    if not pending_routes:
        return {}

    route = pending_routes[0]
    result = _run_tool_for_route(route=route, question=state["question"], state=state)
    route_results = dict(state.get("route_results", {}))
    routes_executed = list(state.get("completed_routes") or state.get("routes_executed", []))
    route_results[route] = result
    routes_executed.append(route)

    return {
        "pending_routes": pending_routes[1:],
        "route_results": route_results,
        "completed_routes": routes_executed,
        "routes_executed": routes_executed,
    }


def _fullstack_loop(state: AgentState) -> Literal["run_next_fullstack_route", "finalize_response"]:
    return "run_next_fullstack_route" if state.get("pending_routes") else "finalize_response"


def _finalize_response_node(state: AgentState) -> dict[str, Any]:
    final_result = _finalize_result(
        question=state["question"],
        settings=state["settings"],
        selected_pipeline=state["selected_pipeline"],
        route_plan=state["route_plan"],
        route_results=state.get("route_results", {}),
        options=state["options"],
    )
    return {"final_result": final_result}


def _build_agent_graph():
    from .graph import build_agent_graph

    return build_agent_graph()


def run_agentic_query(
    settings: AppConfig,
    question: str,
    *,
    user_id: str = "system",
    options: AgenticOptions | None = None,
) -> dict[str, Any]:
    """Competition router for route-specific and fullstack execution via LangGraph."""
    graph = _build_agent_graph()
    final_state = graph.invoke(
        {
            "question": question,
            "settings": settings,
            "user_id": user_id,
            "options": options or AgenticOptions(),
        }
    )
    return dict(final_state["final_result"])
