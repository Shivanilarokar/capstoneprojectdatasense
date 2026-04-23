"""Graph builder for the LangGraph competition orchestrator."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .models import OrchestratorState


def build_agent_graph(
    *,
    init_context_node: Any | None = None,
    authz_guard_node: Any | None = None,
    authz_mode: Any | None = None,
    route_question_node: Any | None = None,
    route_mode: Any | None = None,
    run_single_route_node: Any | None = None,
    plan_fullstack_node: Any | None = None,
    run_parallel_fullstack_routes_node: Any | None = None,
    evidence_validation_node: Any | None = None,
    risk_scoring_node: Any | None = None,
    compliance_output_guard_node: Any | None = None,
    finalize_response_node: Any | None = None,
    checkpointer: Any | None = None,
):
    """Compile the central LangGraph workflow for request orchestration."""
    if route_question_node is None:
        from . import agent as agent_module

        init_context_node = agent_module._init_context_node
        authz_guard_node = agent_module._authz_guard_node
        authz_mode = agent_module._authz_mode
        route_question_node = agent_module._route_question_node
        route_mode = agent_module._route_mode
        run_single_route_node = agent_module._run_single_route_node
        plan_fullstack_node = agent_module._plan_fullstack_node
        run_parallel_fullstack_routes_node = agent_module._run_parallel_fullstack_routes_node
        evidence_validation_node = agent_module._evidence_validation_node
        risk_scoring_node = agent_module._risk_scoring_node
        compliance_output_guard_node = agent_module._compliance_output_guard_node
        finalize_response_node = agent_module._finalize_response_node

    workflow = StateGraph(OrchestratorState)
    workflow.add_node("init_context", init_context_node)
    workflow.add_node("authz_guard", authz_guard_node)
    workflow.add_node("route_question", route_question_node)
    workflow.add_node("run_single_route", run_single_route_node)
    workflow.add_node("plan_fullstack", plan_fullstack_node)
    workflow.add_node("run_parallel_fullstack_routes", run_parallel_fullstack_routes_node)
    workflow.add_node("evidence_validation", evidence_validation_node)
    workflow.add_node("risk_scoring", risk_scoring_node)
    workflow.add_node("compliance_output_guard", compliance_output_guard_node)
    workflow.add_node("finalize_response", finalize_response_node)

    workflow.add_edge(START, "init_context")
    workflow.add_edge("init_context", "authz_guard")
    workflow.add_conditional_edges(
        "authz_guard",
        authz_mode,
        {
            "route_question": "route_question",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_conditional_edges(
        "route_question",
        route_mode,
        {
            "run_single_route": "run_single_route",
            "plan_fullstack": "plan_fullstack",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_edge("run_single_route", "evidence_validation")
    workflow.add_edge("plan_fullstack", "run_parallel_fullstack_routes")
    workflow.add_edge("run_parallel_fullstack_routes", "evidence_validation")
    workflow.add_edge("evidence_validation", "risk_scoring")
    workflow.add_edge("risk_scoring", "compliance_output_guard")
    workflow.add_edge("compliance_output_guard", "finalize_response")
    workflow.add_edge("finalize_response", END)
    return workflow.compile(checkpointer=checkpointer or InMemorySaver())
