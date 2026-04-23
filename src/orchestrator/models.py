"""Typed models shared by the LangGraph orchestrator."""

from __future__ import annotations

from typing import Any

from config import AppConfig
from typing_extensions import TypedDict


class RoutePlan(TypedDict, total=False):
    pipeline: str
    routes: list[str]
    planned_routes: list[str]
    graph_routes: list[str]
    confidence: float
    reason: str
    planner: str
    tool_budget: int
    budget_limited: bool


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


class OrchestratorState(TypedDict, total=False):
    question: str
    settings: AppConfig
    user_id: str
    options: Any
    route_plan: RoutePlan
    selected_pipeline: str
    graph_routes_hint: list[str]
    pending_routes: list[str]
    planned_routes: list[str]
    routes_executed: list[str]
    completed_routes: list[str]
    route_results: dict[str, RouteEnvelope]
    final_result: dict[str, Any]
