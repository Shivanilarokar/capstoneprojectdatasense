"""Typed state definitions for the live LangGraph orchestrator."""

from __future__ import annotations

import operator
from typing import Any, Literal

from typing import Annotated
from typing_extensions import TypedDict

from backend.config import AppConfig


RouteName = Literal["pageindex", "sanctions", "nlsql", "graphrag", "fullstack", "authz_guard"]


class RoutePlan(TypedDict, total=False):
    plan_type: str
    pipeline: str
    routes: list[str]
    planned_routes: list[str]
    graph_routes: list[str]
    confidence: float
    reason: str
    planner: str
    tier_hint: str
    subquestions: list[dict[str, Any]]
    tool_budget: int
    budget_limited: bool
    blocked_by_authz: bool


class RouteEnvelope(TypedDict, total=False):
    status: str
    question: str
    route: str
    tenant_id: str
    answer: str
    evidence: dict[str, Any]
    provenance: dict[str, Any]
    freshness: dict[str, Any]
    warnings: list[str]
    debug: dict[str, Any]


class GraphState(TypedDict, total=False):
    chunking_strategy: str
    question: str
    effective_question: str
    rewritten_question: str
    retrieval_query: str
    web_search_error: str

    route: RouteName
    route_reason: str
    route_hint: str
    initial_route: str
    force_route: bool

    route_plan: RoutePlan
    selected_pipeline: str
    graph_routes_hint: list[str]
    pending_routes: list[str]
    planned_routes: list[str]
    routes_executed: list[str]
    completed_routes: list[str]

    settings: AppConfig
    user_id: str
    options: Any
    correlation_id: str
    query_id: str
    checkpoint_log_path: str
    trace_log_path: str
    trace: dict[str, Any]
    authz: dict[str, Any]
    compliance: dict[str, Any]

    company: str | None
    period: str | None
    source_type: str | None
    data_source_result: dict[str, Any]
    contradiction_report: list[dict[str, Any]]

    route_results: dict[str, RouteEnvelope]
    filtered_route_results: dict[str, RouteEnvelope]
    retrieved_docs: list[dict[str, Any]]
    filtered_docs: list[dict[str, Any]]
    web_results: list[dict[str, Any]]

    answer: str
    citations: list[str]

    route_relevance: list[str]
    doc_relevance: list[str]
    relevant_route_count: int
    relevant_doc_count: int
    rewrite_recommended: bool
    rewrite_reason: str
    rewrite_applied: bool

    hallucination_grade: str
    answer_quality_grade: str

    iteration: int
    max_iterations: int
    retrieval_attempt: int
    max_retrieval_attempts: int
    rewrite_attempts: int

    eval_config: dict[str, Any]

    checkpoints: Annotated[list[dict[str, Any]], operator.add]
    evidence_sufficiency: dict[str, Any]
    risk_score: int
    risk_score_components: dict[str, Any]
    final_result: dict[str, Any]


OrchestratorState = GraphState


__all__ = [
    "GraphState",
    "OrchestratorState",
    "RouteEnvelope",
    "RouteName",
    "RoutePlan",
]
