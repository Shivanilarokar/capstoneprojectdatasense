"""LangGraph-native competition orchestrator for route-specific and fullstack execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from backend.config import AppConfig
from backend.generation.generation import LLMConfig, chat_text
from backend.observability import emit_alert_event, emit_trace_event, write_checkpoint

from . import grader as grader_module
from . import planner as planner_module
from . import query_rewriter as query_rewriter_module
from .contracts import make_result_envelope, normalize_graphrag_result, normalize_nlsql_result, normalize_pageindex_result
from .state import GraphState
from .tools import build_route_tools


@dataclass(frozen=True)
class AgenticOptions:
    """Runtime knobs for central routing/execution."""

    force_pipeline: str | None = None
    use_llm_synthesis: bool = True
    enable_grading: bool = True
    enable_query_rewrite: bool = True
    max_rewrite_attempts: int = 1
    max_answer_iterations: int = 2
    graph_max_results: int = 20
    allowed_pipelines: tuple[str, ...] | None = None
    user_roles: tuple[str, ...] = ("analyst",)
    thread_id: str | None = None
    max_parallel_routes: int = 4

    pageindex_sections_json: Path | None = None
    pageindex_docs_dir: Path | None = None
    pageindex_workspace: Path | None = None
    pageindex_output_dir: Path | None = None

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


AgentState = GraphState


PIPELINE_OPTIONS = ["pageindex", "sanctions", "nlsql", "graphrag", "fullstack"]
MAX_FULLSTACK_ROUTE_CALLS = 4
GRAPH_ALLOWED_ROUTES = ["financial", "sanctions", "trade", "hazard", "regulatory", "cascade"]


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


def _run_pageindex_query(
    settings: AppConfig,
    question: str,
    options: AgenticOptions,
) -> dict[str, Any]:
    from backend.pageindex.pipeline import run_pipeline as run_pageindex_pipeline

    sections_json = _resolve_path(
        settings.project_root,
        options.pageindex_sections_json or settings.pageindex_sections_json,
    )
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
    from backend.sanctions.query import run_sanctions_query

    return run_sanctions_query(settings, question, user_id=user_id)


def _run_nlsql_route(settings: AppConfig, question: str) -> dict[str, Any]:
    from backend.nlsql.query import run_nlsql_query

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
    from backend.graphrag.query import run_graph_query

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
    *,
    regeneration_iteration: int = 0,
) -> str:
    regeneration_note = ""
    if regeneration_iteration > 0:
        regeneration_note = (
            "This is a regeneration pass after answer-grading feedback. "
            "Stay tightly grounded in route evidence and avoid unsupported synthesis.\n"
        )
    prompt = f"""
You are the final answer synthesizer for a supply-chain agentic system.
Merge route outputs into one concise answer. Use sanctions and numeric facts as anchors.
If evidence is missing, explicitly disclose that gap. Preserve trade freshness caveats.
{regeneration_note}

Question:
{question}

Route outputs:
{json.dumps(route_results, ensure_ascii=False)[:70000]}
"""
    return chat_text(llm, prompt, temperature=0)


def _route_results_as_docs(route_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for route, result in route_results.items():
        docs.append(
            {
                "route": route,
                "content": str(result.get("answer", "")),
                "metadata": {
                    "route": route,
                    "provenance": result.get("provenance", {}),
                    "freshness": result.get("freshness", {}),
                },
                "evidence": result.get("evidence", {}),
            }
        )
    return docs


def _collect_citations(route_results: dict[str, dict[str, Any]]) -> list[str]:
    citations: list[str] = []
    for route, result in route_results.items():
        provenance = result.get("provenance", {})
        freshness = result.get("freshness", {})
        if isinstance(provenance, dict):
            if provenance.get("source_table"):
                citations.append(f"{route}:{provenance['source_table']}")
            elif provenance.get("graph_routes"):
                citations.extend(f"{route}:{item}" for item in provenance.get("graph_routes", []) if item)
            elif provenance.get("sql"):
                citations.append(f"{route}:sql")
        if isinstance(freshness, dict) and freshness.get("latest_loaded_at"):
            citations.append(f"{route}:{freshness['latest_loaded_at']}")
    deduped: list[str] = []
    for citation in citations:
        if citation not in deduped:
            deduped.append(citation)
    return deduped


def _checkpoint_update(state: AgentState, node_name: str, **extra: Any) -> dict[str, Any]:
    snapshot = {
        "question": state.get("question"),
        "effective_question": state.get("effective_question", state.get("question")),
        "selected_pipeline": state.get("selected_pipeline"),
        "planned_routes": state.get("planned_routes", []),
        "completed_routes": state.get("completed_routes", []),
        "rewrite_attempts": state.get("rewrite_attempts", 0),
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
    filtered_route_results: dict[str, dict[str, Any]],
    answer: str,
    citations: list[str],
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
    hallucination_grade: str,
    answer_quality_grade: str,
    retrieval_attempt: int,
    iteration: int,
) -> dict[str, Any]:
    routes_executed = list(route_results.keys())
    planned_routes = list(route_plan.get("planned_routes") or route_plan.get("routes") or routes_executed)
    if not routes_executed:
        envelope = make_result_envelope(
            question=question,
            route=selected_pipeline or "fullstack",
            answer=answer,
            warnings=["No route outputs were available during finalization."],
            debug={"route_plan": route_plan},
            tenant_id=settings.graph_tenant_id,
        )
    elif selected_pipeline == "fullstack":
        warnings = [warning for result in route_results.values() for warning in result.get("warnings", [])]
        freshness = {route: result.get("freshness", {}) for route, result in route_results.items()}
        provenance = {route: result.get("provenance", {}) for route, result in route_results.items()}
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
        envelope["answer"] = answer

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
            "filtered_route_results": filtered_route_results,
            "correlation_id": correlation_id,
            "query_id": query_id,
            "checkpoint_log_path": checkpoint_log_path,
            "checkpoints": checkpoints,
            "trace": trace,
            "evidence_sufficiency": evidence_sufficiency,
            "risk_score": risk_score,
            "risk_score_components": risk_score_components,
            "compliance": compliance,
            "answer": answer,
            "citations": citations,
            "hallucination_grade": hallucination_grade,
            "answer_quality_grade": answer_quality_grade,
            "retrieval_attempt": retrieval_attempt,
            "answer_iterations": iteration,
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
        "route": "",
        "route_reason": "",
        "route_hint": "",
        "initial_route": "",
        "force_route": bool(options.force_pipeline),
        "effective_question": state["question"],
        "retrieval_query": state["question"],
        "rewritten_question": "",
        "answer": "",
        "citations": [],
        "retrieved_docs": [],
        "filtered_docs": [],
        "web_results": [],
        "rewrite_attempts": 0,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": max(0, options.max_rewrite_attempts),
        "iteration": 0,
        "max_iterations": max(0, options.max_answer_iterations),
        "rewrite_applied": False,
        "filtered_route_results": {},
        "route_relevance": [],
        "doc_relevance": [],
        "relevant_route_count": 0,
        "relevant_doc_count": 0,
        "rewrite_recommended": False,
        "rewrite_reason": "",
        "hallucination_grade": "",
        "answer_quality_grade": "",
        "eval_config": {},
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

    llm = LLMConfig(api_key=settings.openai_api_key, model=settings.openai_model) if settings.openai_api_key else None
    sections_json = _resolve_path(
        settings.project_root,
        options.pageindex_sections_json or settings.pageindex_sections_json,
    )
    pageindex_tickers = _load_pageindex_tickers(sections_json)
    base_plan = planner_module.plan_query(question, llm=llm, pageindex_tickers=pageindex_tickers)

    forced = _normalize_pipeline(options.force_pipeline) if options.force_pipeline else ""
    if forced:
        route_plan = dict(base_plan)
        route_plan.update(
            {
                "pipeline": forced,
                "routes": base_plan.get("routes", []) if forced == "fullstack" else [forced],
                "confidence": 1.0,
                "reason": "Pipeline forced by caller override.",
                "planner": "forced",
            }
        )
    else:
        route_plan = dict(base_plan)

    selected_pipeline = route_plan["pipeline"]
    graph_routes_hint = _normalize_routes(route_plan.get("graph_routes", []))
    pending_routes = list(route_plan.get("routes", []))
    if selected_pipeline != "fullstack":
        pending_routes = [selected_pipeline]
    elif not pending_routes:
        pending_routes = ["nlsql", "graphrag"]

    bounded = _bounded_routes(pending_routes)
    if selected_pipeline == "fullstack":
        bounded = [route for route in bounded if route in allowed]
        if not bounded:
            route_plan["blocked_by_authz"] = True
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
        "route": selected_pipeline,
        "route_reason": str(route_plan.get("reason", "")),
        "route_hint": ",".join(graph_routes_hint),
        "initial_route": selected_pipeline,
        "route_plan": route_plan,
        "selected_pipeline": selected_pipeline,
        "graph_routes_hint": graph_routes_hint,
        "pending_routes": bounded,
        "planned_routes": planned_routes,
        "route_results": {},
        "filtered_route_results": {},
        "retrieved_docs": [],
        "filtered_docs": [],
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
    effective_question = state.get("effective_question", state["question"])
    result = _run_tool_for_route(route=route, question=effective_question, state=state)
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
    effective_question = state.get("effective_question", state["question"])
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
            route: executor.submit(_run_tool_for_route, route=route, question=effective_question, state=state)
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


def _grade_route_results_node(state: AgentState) -> dict[str, Any]:
    route_results = state.get("route_results", {})
    retrieved_docs = _route_results_as_docs(route_results)
    if not route_results:
        update = {
            "filtered_route_results": {},
            "retrieved_docs": [],
            "filtered_docs": [],
            "route_relevance": [],
            "doc_relevance": [],
            "relevant_route_count": 0,
            "relevant_doc_count": 0,
            "rewrite_recommended": False,
            "rewrite_reason": "No route outputs were available to grade.",
        }
    elif not state["options"].enable_grading:
        update = {
            "filtered_route_results": route_results,
            "retrieved_docs": retrieved_docs,
            "filtered_docs": retrieved_docs,
            "route_relevance": ["yes"] * len(route_results),
            "doc_relevance": ["yes"] * len(route_results),
            "relevant_route_count": len(route_results),
            "relevant_doc_count": len(route_results),
            "rewrite_recommended": False,
            "rewrite_reason": "",
        }
    else:
        update = grader_module.grade_route_results(state)
        filtered_route_results = update.get("filtered_route_results", {})
        update["retrieved_docs"] = retrieved_docs
        update["filtered_docs"] = _route_results_as_docs(filtered_route_results)
    update.update(
        _checkpoint_update(
            state,
            "grade_route_results",
            relevant_route_count=update.get("relevant_route_count", 0),
            rewrite_recommended=update.get("rewrite_recommended", False),
        )
    )
    return update


def _grade_route_results_mode(state: AgentState) -> Literal["rewrite_query", "evidence_validation"]:
    options = state["options"]
    if not options.enable_grading:
        return "evidence_validation"
    if not state.get("rewrite_recommended"):
        return "evidence_validation"
    if not options.enable_query_rewrite:
        return "evidence_validation"
    if state.get("rewrite_attempts", 0) >= max(0, options.max_rewrite_attempts):
        return "evidence_validation"
    return "rewrite_query"


def _rewrite_query_node(state: AgentState) -> dict[str, Any]:
    rewritten = query_rewriter_module.rewrite_query(state)
    previous_effective_question = state.get("effective_question", state["question"])
    next_effective_question = rewritten.get("effective_question", previous_effective_question)
    rewrite_applied = bool(
        rewritten.get(
            "rewrite_applied",
            str(next_effective_question).strip().lower() != str(previous_effective_question).strip().lower(),
        )
    )
    update = {
        "retrieval_query": rewritten.get("retrieval_query", previous_effective_question),
        "rewritten_question": rewritten.get("rewritten_question", state.get("rewritten_question", "")),
        "effective_question": next_effective_question,
        "rewrite_applied": rewrite_applied,
        "rewrite_attempts": state.get("rewrite_attempts", 0) + 1,
    }
    if rewrite_applied:
        update.update(
            {
                "route_results": {},
                "filtered_route_results": {},
                "retrieved_docs": [],
                "filtered_docs": [],
                "completed_routes": [],
                "routes_executed": [],
                "pending_routes": list(state.get("planned_routes", [])),
                "route_relevance": [],
                "doc_relevance": [],
                "relevant_route_count": 0,
                "relevant_doc_count": 0,
                "evidence_sufficiency": {},
                "answer": "",
                "citations": [],
                "hallucination_grade": "",
                "answer_quality_grade": "",
            }
        )
    update.update(
        _checkpoint_update(
            state,
            "rewrite_query",
            rewrite_applied=rewrite_applied,
            effective_question=update["effective_question"],
        )
    )
    return update


def _rewrite_mode(state: AgentState) -> Literal["run_single_route", "plan_fullstack", "evidence_validation"]:
    if not state.get("rewrite_applied"):
        return "evidence_validation"
    return "plan_fullstack" if state["selected_pipeline"] == "fullstack" else "run_single_route"


def _evidence_validation_node(state: AgentState) -> dict[str, Any]:
    planned_routes = list(state.get("planned_routes", []))
    route_results = state.get("filtered_route_results") or state.get("route_results", {})
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
        "relevant_route_count": state.get("relevant_route_count", len(route_results)),
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
    route_results = state.get("filtered_route_results") or state.get("route_results", {})
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
    route_results = state.get("filtered_route_results") or state.get("route_results", {})
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


def _generate_response_node(state: AgentState) -> dict[str, Any]:
    route_results = state.get("filtered_route_results") or state.get("route_results", {})
    if not route_results:
        answer = _apply_compliance_answer_policy(
            "No sufficiently relevant evidence was retrieved for this question.",
            state.get("compliance", {"checked": False, "flags": []}),
            state.get("evidence_sufficiency", {}),
        )
        citations: list[str] = []
    elif state.get("selected_pipeline") == "fullstack":
        if state["settings"].openai_api_key and state["options"].use_llm_synthesis:
            llm = LLMConfig(api_key=state["settings"].openai_api_key, model=state["settings"].openai_model)
            try:
                answer = _synthesize_fullstack_answer(
                    state["question"],
                    route_results,
                    llm,
                    regeneration_iteration=state.get("iteration", 0),
                )
            except Exception:
                answer = _fallback_fullstack_answer(state["question"], route_results)
        else:
            answer = _fallback_fullstack_answer(state["question"], route_results)
        answer = _apply_compliance_answer_policy(answer, state.get("compliance", {}), state.get("evidence_sufficiency", {}))
        citations = _collect_citations(route_results)
    else:
        primary_route = state.get("selected_pipeline")
        primary_result = route_results.get(str(primary_route), {})
        answer = _apply_compliance_answer_policy(
            str(primary_result.get("answer", "")).strip() or "No answer was returned by the selected route.",
            state.get("compliance", {}),
            state.get("evidence_sufficiency", {}),
        )
        citations = _collect_citations({str(primary_route): primary_result}) if primary_result else []

    update = {
        "answer": answer,
        "citations": citations,
    }
    update.update(
        _checkpoint_update(
            state,
            "generate_response",
            iteration=state.get("iteration", 0),
            answer_chars=len(answer),
        )
    )
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
        filtered_route_results=state.get("filtered_route_results", {}),
        answer=state.get("answer", ""),
        citations=list(state.get("citations", [])),
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
        hallucination_grade=state.get("hallucination_grade", ""),
        answer_quality_grade=state.get("answer_quality_grade", ""),
        retrieval_attempt=state.get("retrieval_attempt", 0),
        iteration=state.get("iteration", 0),
    )
    warnings = list(final_result.get("warnings", []))
    compliance = dict(final_result.get("compliance", state.get("compliance", {"checked": False, "flags": []})))
    flags = list(compliance.get("flags", []))
    if state.get("hallucination_grade") == "no" and "answer_not_grounded" not in flags:
        flags.append("answer_not_grounded")
        warnings.append("Final answer grounding is weak relative to the available route evidence.")
    if state.get("answer_quality_grade") == "no" and "answer_quality_low" not in flags:
        flags.append("answer_quality_low")
        warnings.append("Final answer quality is weak relative to the user question.")
    compliance["flags"] = flags
    final_result["warnings"] = list(dict.fromkeys(warnings))
    final_result["compliance"] = compliance
    final_result["effective_question"] = state.get("effective_question", state["question"])
    final_result["rewrite_attempts"] = state.get("rewrite_attempts", 0)
    if state.get("rewritten_question"):
        final_result["rewritten_question"] = state["rewritten_question"]
    if state.get("route_relevance"):
        final_result["route_relevance"] = list(state["route_relevance"])
    if state.get("doc_relevance"):
        final_result["doc_relevance"] = list(state["doc_relevance"])
    update = {"final_result": final_result}
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
    update.update(
        _checkpoint_update(
            state,
            "finalize_response",
            hallucination_grade=state.get("hallucination_grade", ""),
            answer_quality_grade=state.get("answer_quality_grade", ""),
        )
    )
    return update


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
