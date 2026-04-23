"""LangGraph-native competition orchestrator for route-specific and fullstack execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from generation.generation import LLMConfig, chat_json, chat_text
from config import AppConfig
from observability import emit_alert_event, emit_trace_event, write_checkpoint

from .contracts import make_result_envelope, normalize_graphrag_result, normalize_nlsql_result, normalize_pageindex_result
from .models import OrchestratorState
from .tools import build_route_tools


@dataclass(frozen=True)
class AgenticOptions:
    """Runtime knobs for central routing/execution."""

    force_pipeline: str | None = None
    use_llm_synthesis: bool = True
    graph_max_results: int = 20
    allowed_pipelines: tuple[str, ...] | None = None
    user_roles: tuple[str, ...] = ("analyst",)
    thread_id: str | None = None
    max_parallel_routes: int = 4

    pageindex_sections_json: Path = Path("data/ingestion/sec/extracted_10k_sections.json")
    pageindex_docs_dir: Path = Path("data/pageindex/docs")
    pageindex_workspace: Path = Path("data/pageindex/workspace")
    pageindex_output_dir: Path = Path("data/pageindex/output")

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
    docs_dir = _resolve_path(settings.project_root, options.pageindex_docs_dir or settings.pageindex_docs_dir)
    workspace = _resolve_path(settings.project_root, options.pageindex_workspace or settings.pageindex_workspace_dir)
    output_dir = _resolve_path(settings.project_root, options.pageindex_output_dir or settings.pageindex_output_dir)

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


def _checkpoint_update(state: AgentState, node_name: str, **extra: Any) -> dict[str, Any]:
    snapshot = {
        "question": state.get("question"),
        "selected_pipeline": state.get("selected_pipeline"),
        "planned_routes": state.get("planned_routes", []),
        "completed_routes": state.get("completed_routes", []),
        **extra,
    }
    path = Path(str(state["checkpoint_log_path"]))
    record = write_checkpoint(path, node_name, snapshot)
    emit_trace_event(
        Path(str(state["trace_log_path"])),
        "langgraph_node_completed",
        state["correlation_id"],
        {"node": node_name, "snapshot": snapshot},
    )
    return {
        "checkpoints": [
            {
                "node": node_name,
                "timestamp_utc": record["timestamp_utc"],
            }
        ]
    }


def _apply_compliance_answer_policy(answer: str, compliance: dict[str, Any], evidence_sufficiency: dict[str, Any]) -> str:
    guarded = answer.strip()
    flags = set(compliance.get("flags", []))
    if "human_review_required" in flags:
        guarded = f"Analyst review required before acting on this result.\n\n{guarded}"
    if not evidence_sufficiency.get("ok"):
        guarded = f"{guarded}\n\nEvidence coverage is incomplete; treat this answer as provisional."
    return guarded


def _finalize_result(
    *,
    question: str,
    settings: AppConfig,
    selected_pipeline: str,
    route_plan: dict[str, Any],
    route_results: dict[str, dict[str, Any]],
    options: AgenticOptions,
    correlation_id: str,
    query_id: str,
    checkpoints: list[dict[str, Any]],
    checkpoint_log_path: str,
    trace: dict[str, Any],
    evidence_sufficiency: dict[str, Any],
    risk_score: int,
    risk_score_components: dict[str, Any],
    compliance: dict[str, Any],
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
        answer = _apply_compliance_answer_policy(answer, compliance, evidence_sufficiency)
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
        envelope["answer"] = _apply_compliance_answer_policy(str(envelope.get("answer", "")), compliance, evidence_sufficiency)

    envelope.update(
        {
            "status": envelope.get("status", "ok"),
            "question": question,
            "tenant_id": settings.graph_tenant_id,
            "selected_pipeline": selected_pipeline,
            "route_plan": route_plan,
            "planned_routes": planned_routes,
            "completed_routes": routes_executed,
            "routes_executed": routes_executed,
            "route_results": route_results,
            "correlation_id": correlation_id,
            "query_id": query_id,
            "checkpoint_log_path": checkpoint_log_path,
            "checkpoints": checkpoints,
            "trace": trace,
            "evidence_sufficiency": evidence_sufficiency,
            "risk_score": risk_score,
            "risk_score_components": risk_score_components,
            "compliance": compliance,
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


def _init_context_node(state: AgentState) -> dict[str, Any]:
    settings = state["settings"]
    options = state["options"]
    query_id = str(uuid4())
    correlation_id = str(uuid4())
    thread_id = options.thread_id or query_id
    checkpoint_log_path = settings.observability_dir / "langgraph_checkpoints" / f"{thread_id}.jsonl"
    trace_log_path = settings.observability_dir / "traces" / f"{thread_id}.jsonl"
    emit_trace_event(
        trace_log_path,
        "query_started",
        correlation_id,
        {
            "query_id": query_id,
            "tenant_id": settings.graph_tenant_id,
            "user_id": state["user_id"],
            "user_roles": list(options.user_roles),
            "langsmith_tracing": settings.langsmith_tracing,
            "langsmith_project": settings.langsmith_project,
        },
    )
    checkpoint = write_checkpoint(
        checkpoint_log_path,
        "init_context",
        {
            "question": state["question"],
            "tenant_id": settings.graph_tenant_id,
            "thread_id": thread_id,
        },
    )
    return {
        "correlation_id": correlation_id,
        "query_id": query_id,
        "checkpoint_log_path": str(checkpoint_log_path),
        "trace_log_path": str(trace_log_path),
        "trace": {
            "thread_id": thread_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "langsmith_tracing": settings.langsmith_tracing,
            "langsmith_project": settings.langsmith_project,
        },
        "authz": {
            "roles": list(options.user_roles),
            "allowed_pipelines": list(options.allowed_pipelines or PIPELINE_OPTIONS),
            "tenant_id": settings.graph_tenant_id,
        },
        "checkpoints": [{"node": "init_context", "timestamp_utc": checkpoint["timestamp_utc"]}],
        "compliance": {"checked": False, "flags": []},
    }


def _authz_guard_node(state: AgentState) -> dict[str, Any]:
    settings = state["settings"]
    options = state["options"]
    allowed = set(options.allowed_pipelines or PIPELINE_OPTIONS)
    forced = _normalize_pipeline(options.force_pipeline) if options.force_pipeline else ""
    if forced and forced not in allowed:
        compliance = {
            "checked": True,
            "flags": ["pipeline_not_authorized"],
            "blocked_by": "authz_guard",
        }
        final_result = make_result_envelope(
            question=state["question"],
            route="authz_guard",
            answer=f"Pipeline `{forced}` is not authorized for roles {list(options.user_roles)}.",
            status="denied",
            warnings=["Requested pipeline is not authorized for the current caller context."],
            debug={"allowed_pipelines": sorted(allowed), "roles": list(options.user_roles)},
            tenant_id=settings.graph_tenant_id,
        )
        final_result.update(
            {
                "selected_pipeline": forced,
                "planned_routes": [],
                "completed_routes": [],
                "routes_executed": [],
                "route_results": {},
                "correlation_id": state["correlation_id"],
                "query_id": state["query_id"],
                "checkpoint_log_path": state["checkpoint_log_path"],
                "trace": state["trace"],
                "checkpoints": state.get("checkpoints", []),
                "evidence_sufficiency": {"ok": False, "score": 0.0, "warnings": ["Authorization denied."]},
                "risk_score": 0,
                "risk_score_components": {},
                "compliance": compliance,
            }
        )
        emit_alert_event(
            settings.alert_event_log,
            "authz_denied",
            state["correlation_id"],
            {"query_id": state["query_id"], "requested_pipeline": forced, "roles": list(options.user_roles)},
        )
        update = {"final_result": final_result, "compliance": compliance}
        update.update(_checkpoint_update(state, "authz_guard", authorized=False, requested_pipeline=forced))
        return update

    update = {"authz": {**state.get("authz", {}), "authorized": True}}
    update.update(_checkpoint_update(state, "authz_guard", authorized=True))
    return update


def _authz_mode(state: AgentState) -> Literal["route_question", "finalize_response"]:
    return "finalize_response" if state.get("final_result") else "route_question"


def _route_question_node(state: AgentState) -> dict[str, Any]:
    settings = state["settings"]
    question = state["question"]
    options = state["options"]
    allowed = set(options.allowed_pipelines or PIPELINE_OPTIONS)

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
    if selected_pipeline == "fullstack":
        bounded = [route for route in bounded if route in allowed]
        if not bounded:
            route_plan["blocked_by_authz"] = True
            selected_pipeline = "fullstack"
    elif selected_pipeline not in allowed:
        route_plan["blocked_by_authz"] = True
        bounded = []
    planned_routes = bounded if selected_pipeline == "fullstack" else ([] if route_plan.get("blocked_by_authz") else [selected_pipeline])
    route_plan["routes"] = planned_routes
    route_plan["planned_routes"] = planned_routes
    route_plan["tool_budget"] = MAX_FULLSTACK_ROUTE_CALLS if selected_pipeline == "fullstack" else 1
    if selected_pipeline == "fullstack" and len(bounded) < len(pending_routes):
        route_plan["budget_limited"] = True
    final_result = None
    if route_plan.get("blocked_by_authz") and not planned_routes:
        compliance = {
            "checked": True,
            "flags": ["pipeline_not_authorized"],
            "blocked_by": "route_question",
        }
        final_result = make_result_envelope(
            question=question,
            route="authz_guard",
            answer="No authorized pipeline remains after policy filtering.",
            status="denied",
            warnings=["The selected route plan was blocked by pipeline authorization rules."],
            debug={"allowed_pipelines": sorted(allowed)},
            tenant_id=settings.graph_tenant_id,
        )
        final_result.update(
            {
                "selected_pipeline": selected_pipeline,
                "planned_routes": [],
                "completed_routes": [],
                "routes_executed": [],
                "route_results": {},
                "correlation_id": state["correlation_id"],
                "query_id": state["query_id"],
                "checkpoint_log_path": state["checkpoint_log_path"],
                "trace": state["trace"],
                "checkpoints": state.get("checkpoints", []),
                "evidence_sufficiency": {"ok": False, "score": 0.0, "warnings": ["Authorization denied."]},
                "risk_score": 0,
                "risk_score_components": {},
                "compliance": compliance,
            }
        )
    update = {
        "route_plan": route_plan,
        "selected_pipeline": selected_pipeline,
        "graph_routes_hint": graph_routes_hint,
        "pending_routes": bounded,
        "planned_routes": planned_routes,
        "route_results": {},
        "completed_routes": [],
        "routes_executed": [],
        "final_result": final_result,
    }
    update.update(_checkpoint_update(state, "route_question", selected_pipeline=selected_pipeline, planned_routes=planned_routes))
    return update

def _route_mode(state: AgentState) -> Literal["run_single_route", "plan_fullstack", "finalize_response"]:
    if state.get("final_result"):
        return "finalize_response"
    return "plan_fullstack" if state["selected_pipeline"] == "fullstack" else "run_single_route"


def _run_single_route_node(state: AgentState) -> dict[str, Any]:
    route = state["selected_pipeline"]
    result = _run_tool_for_route(route=route, question=state["question"], state=state)
    update = {
        "route_results": {route: result},
        "completed_routes": [route],
        "routes_executed": [route],
        "pending_routes": [],
    }
    update.update(_checkpoint_update(state, "run_single_route", route=route))
    return update


def _plan_fullstack_node(state: AgentState) -> dict[str, Any]:
    planned_routes = _bounded_routes(state.get("pending_routes", []))
    route_plan = dict(state["route_plan"])
    route_plan["routes"] = planned_routes
    route_plan["planned_routes"] = planned_routes
    update = {
        "pending_routes": planned_routes,
        "planned_routes": planned_routes,
        "route_plan": route_plan,
    }
    update.update(_checkpoint_update(state, "plan_fullstack", planned_routes=planned_routes))
    return update


def _run_parallel_fullstack_routes_node(state: AgentState) -> dict[str, Any]:
    pending_routes = list(state.get("pending_routes", []))
    if not pending_routes:
        update = {
            "pending_routes": [],
            "route_results": {},
            "completed_routes": [],
            "routes_executed": [],
        }
        update.update(_checkpoint_update(state, "run_parallel_fullstack_routes", routes=[]))
        return update

    route_results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(len(pending_routes), state["options"].max_parallel_routes))) as executor:
        futures = {
            route: executor.submit(_run_tool_for_route, route=route, question=state["question"], state=state)
            for route in pending_routes
        }
        for route in pending_routes:
            route_results[route] = futures[route].result()

    update = {
        "pending_routes": [],
        "route_results": route_results,
        "completed_routes": pending_routes,
        "routes_executed": pending_routes,
    }
    update.update(_checkpoint_update(state, "run_parallel_fullstack_routes", routes=pending_routes))
    return update


def _evidence_validation_node(state: AgentState) -> dict[str, Any]:
    planned_routes = list(state.get("planned_routes", []))
    route_results = state.get("route_results", {})
    answered_routes = [route for route, result in route_results.items() if str(result.get("answer", "")).strip()]
    evidence_routes = [route for route, result in route_results.items() if result.get("evidence")]
    provenance_routes = [route for route, result in route_results.items() if result.get("provenance")]
    missing_routes = [route for route in planned_routes if route not in route_results]
    target_answers = max(1, min(2, len(planned_routes))) if state.get("selected_pipeline") == "fullstack" else 1
    ok = len(answered_routes) >= target_answers and len(provenance_routes) >= 1
    score = round(
        (len(answered_routes) + len(evidence_routes) + len(provenance_routes)) / max(1, len(planned_routes) * 3),
        4,
    )
    warnings: list[str] = []
    if missing_routes:
        warnings.append(f"Missing route outputs for: {', '.join(missing_routes)}.")
    if not ok:
        warnings.append("Evidence sufficiency threshold not met.")
    evidence_sufficiency = {
        "ok": ok,
        "score": score,
        "answered_routes": answered_routes,
        "evidence_routes": evidence_routes,
        "provenance_routes": provenance_routes,
        "missing_routes": missing_routes,
        "warnings": warnings,
    }
    if not ok:
        emit_alert_event(
            state["settings"].alert_event_log,
            "insufficient_evidence",
            state["correlation_id"],
            {"query_id": state["query_id"], "planned_routes": planned_routes, "answered_routes": answered_routes},
        )
    update = {"evidence_sufficiency": evidence_sufficiency}
    update.update(_checkpoint_update(state, "evidence_validation", evidence_ok=ok, evidence_score=score))
    return update


def _risk_scoring_node(state: AgentState) -> dict[str, Any]:
    route_results = state.get("route_results", {})
    sanctions_result = route_results.get("sanctions", {})
    sanctions_evidence = sanctions_result.get("evidence", {})
    graphrag_result = route_results.get("graphrag", {})
    pageindex_result = route_results.get("pageindex", {})
    nlsql_result = route_results.get("nlsql", {})
    sanctions_score = 50 if sanctions_evidence.get("matches") else 25 if sanctions_evidence.get("review_candidates") else 0
    graph_score = 20 if graphrag_result.get("evidence", {}).get("results") or graphrag_result.get("evidence", {}).get("routes") else 0
    filing_score = 10 if pageindex_result.get("evidence", {}).get("qa_result") else 0
    structured_score = 20 if nlsql_result.get("evidence", {}).get("rows") else 0
    components = {
        "sanctions": sanctions_score,
        "graph": graph_score,
        "filings": filing_score,
        "structured": structured_score,
    }
    risk_score = min(100, sum(components.values()))
    update = {
        "risk_score": risk_score,
        "risk_score_components": components,
    }
    update.update(_checkpoint_update(state, "risk_scoring", risk_score=risk_score, risk_score_components=components))
    return update


def _compliance_output_guard_node(state: AgentState) -> dict[str, Any]:
    route_results = state.get("route_results", {})
    flags: list[str] = []
    sanctions_result = route_results.get("sanctions", {})
    sanctions_evidence = sanctions_result.get("evidence", {})
    if sanctions_evidence.get("review_candidates"):
        flags.append("human_review_required")
    if not state.get("evidence_sufficiency", {}).get("ok"):
        flags.append("insufficient_evidence")
    if state.get("risk_score", 0) >= 70:
        flags.append("high_risk_case")
    compliance = {
        "checked": True,
        "flags": flags,
        "blocked_by": None,
    }
    if flags:
        emit_alert_event(
            state["settings"].alert_event_log,
            "compliance_flagged",
            state["correlation_id"],
            {"query_id": state["query_id"], "flags": flags, "risk_score": state.get("risk_score", 0)},
        )
    update = {"compliance": compliance}
    update.update(_checkpoint_update(state, "compliance_output_guard", flags=flags))
    return update


def _finalize_response_node(state: AgentState) -> dict[str, Any]:
    if state.get("final_result"):
        return {"final_result": state["final_result"]}
    final_result = _finalize_result(
        question=state["question"],
        settings=state["settings"],
        selected_pipeline=state["selected_pipeline"],
        route_plan=state["route_plan"],
        route_results=state.get("route_results", {}),
        options=state["options"],
        correlation_id=state["correlation_id"],
        query_id=state["query_id"],
        checkpoints=list(state.get("checkpoints", [])),
        checkpoint_log_path=str(state["checkpoint_log_path"]),
        trace=state.get("trace", {}),
        evidence_sufficiency=state.get("evidence_sufficiency", {}),
        risk_score=int(state.get("risk_score", 0)),
        risk_score_components=state.get("risk_score_components", {}),
        compliance=state.get("compliance", {"checked": False, "flags": []}),
    )
    emit_trace_event(
        Path(str(state["trace_log_path"])),
        "query_finished",
        state["correlation_id"],
        {
            "query_id": state["query_id"],
            "selected_pipeline": final_result.get("selected_pipeline"),
            "routes_executed": final_result.get("routes_executed", []),
            "risk_score": final_result.get("risk_score", 0),
        },
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
    active_options = options or AgenticOptions()
    final_state = graph.invoke(
        {
            "question": question,
            "settings": settings,
            "user_id": user_id,
            "options": active_options,
        },
        {
            "configurable": {
                "thread_id": active_options.thread_id or str(uuid4()),
            }
        },
    )
    return dict(final_state["final_result"])
