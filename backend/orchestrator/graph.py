"""Graph builder for the LangGraph competition orchestrator."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .state import GraphState


def build_agent_graph(
    *,
    init_context_node: Any | None = None,
    authz_guard_node: Any | None = None,
    authz_mode: Any | None = None,
    route_question_node: Any | None = None,
    run_single_route_node: Any | None = None,
    plan_fullstack_node: Any | None = None,
    run_parallel_fullstack_routes_node: Any | None = None,
    grade_route_results_node: Any | None = None,
    rewrite_query_node: Any | None = None,
    increment_retrieval_attempt_node: Any | None = None,
    evidence_validation_node: Any | None = None,
    risk_scoring_node: Any | None = None,
    compliance_output_guard_node: Any | None = None,
    generate_response_node: Any | None = None,
    grade_hallucination_node: Any | None = None,
    grade_answer_quality_node: Any | None = None,
    increment_iteration_node: Any | None = None,
    finalize_response_node: Any | None = None,
    checkpointer: Any | None = None,
):
    """Compile the central LangGraph workflow for request orchestration."""
    if route_question_node is None:
        from . import router as agent_module
        from . import grader as grader_module

        init_context_node = agent_module._init_context_node
        authz_guard_node = agent_module._authz_guard_node
        authz_mode = agent_module._authz_mode
        route_question_node = agent_module._route_question_node
        run_single_route_node = agent_module._run_single_route_node
        plan_fullstack_node = agent_module._plan_fullstack_node
        run_parallel_fullstack_routes_node = agent_module._run_parallel_fullstack_routes_node
        grade_route_results_node = agent_module._grade_route_results_node
        rewrite_query_node = agent_module._rewrite_query_node
        increment_retrieval_attempt_node = _increment_retrieval_attempt
        evidence_validation_node = agent_module._evidence_validation_node
        risk_scoring_node = agent_module._risk_scoring_node
        compliance_output_guard_node = agent_module._compliance_output_guard_node
        generate_response_node = agent_module._generate_response_node
        grade_hallucination_node = grader_module.grade_hallucination
        grade_answer_quality_node = grader_module.grade_answer_quality
        increment_iteration_node = _increment_iteration
        finalize_response_node = agent_module._finalize_response_node

    workflow = StateGraph(GraphState)
    workflow.add_node("init_context", init_context_node)
    workflow.add_node("authz_guard", authz_guard_node)
    workflow.add_node("route_question", route_question_node)
    workflow.add_node("run_single_route", run_single_route_node)
    workflow.add_node("plan_fullstack", plan_fullstack_node)
    workflow.add_node("run_parallel_fullstack_routes", run_parallel_fullstack_routes_node)
    workflow.add_node("grade_route_results", grade_route_results_node)
    workflow.add_node("rewrite_query", rewrite_query_node)
    workflow.add_node("increment_retrieval_attempt", increment_retrieval_attempt_node)
    workflow.add_node("evidence_validation", evidence_validation_node)
    workflow.add_node("risk_scoring", risk_scoring_node)
    workflow.add_node("compliance_output_guard", compliance_output_guard_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("grade_hallucination", grade_hallucination_node)
    workflow.add_node("grade_answer_quality", grade_answer_quality_node)
    workflow.add_node("increment_iteration", increment_iteration_node)
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
        _route_after_router,
        {
            "run_single_route": "run_single_route",
            "plan_fullstack": "plan_fullstack",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_edge("run_single_route", "grade_route_results")
    workflow.add_edge("plan_fullstack", "run_parallel_fullstack_routes")
    workflow.add_edge("run_parallel_fullstack_routes", "grade_route_results")
    workflow.add_conditional_edges(
        "grade_route_results",
        _route_after_result_grading,
        {
            "rewrite_query": "rewrite_query",
            "evidence_validation": "evidence_validation",
        },
    )
    workflow.add_edge("rewrite_query", "increment_retrieval_attempt")
    workflow.add_conditional_edges(
        "increment_retrieval_attempt",
        _route_after_rewrite,
        {
            "run_single_route": "run_single_route",
            "plan_fullstack": "plan_fullstack",
            "evidence_validation": "evidence_validation",
        },
    )
    workflow.add_edge("evidence_validation", "risk_scoring")
    workflow.add_edge("risk_scoring", "compliance_output_guard")
    workflow.add_edge("compliance_output_guard", "generate_response")
    workflow.add_edge("generate_response", "grade_hallucination")
    workflow.add_conditional_edges(
        "grade_hallucination",
        _route_after_hallucination,
        {
            "grade_answer_quality": "grade_answer_quality",
            "retry_generation": "increment_iteration",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_conditional_edges(
        "grade_answer_quality",
        _route_after_quality,
        {
            "retry_generation": "increment_iteration",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_edge("increment_iteration", "generate_response")
    workflow.add_edge("finalize_response", END)
    return workflow.compile(checkpointer=checkpointer or InMemorySaver())


def _increment_iteration(state: GraphState) -> GraphState:
    return {"iteration": state.get("iteration", 0) + 1}


def _increment_retrieval_attempt(state: GraphState) -> GraphState:
    if not state.get("rewrite_applied"):
        return {}
    return {"retrieval_attempt": state.get("retrieval_attempt", 0) + 1}


def _route_after_router(state: GraphState) -> Literal["run_single_route", "plan_fullstack", "finalize_response"]:
    if state.get("final_result"):
        return "finalize_response"
    return "plan_fullstack" if state.get("selected_pipeline") == "fullstack" else "run_single_route"


def _route_after_result_grading(state: GraphState) -> Literal["rewrite_query", "evidence_validation"]:
    if state.get("relevant_route_count", 0) > 0:
        return "evidence_validation"
    if not state.get("rewrite_recommended"):
        return "evidence_validation"
    if state.get("retrieval_attempt", 0) >= state.get("max_retrieval_attempts", 1):
        return "evidence_validation"
    return "rewrite_query"


def _route_after_rewrite(state: GraphState) -> Literal["run_single_route", "plan_fullstack", "evidence_validation"]:
    if not state.get("rewrite_applied"):
        return "evidence_validation"
    return "plan_fullstack" if state.get("selected_pipeline") == "fullstack" else "run_single_route"


def _route_after_hallucination(state: GraphState) -> Literal["grade_answer_quality", "retry_generation", "finalize_response"]:
    if state.get("hallucination_grade") == "yes":
        return "grade_answer_quality"
    if state.get("iteration", 0) >= state.get("max_iterations", 2):
        return "finalize_response"
    return "retry_generation"


def _route_after_quality(state: GraphState) -> Literal["retry_generation", "finalize_response"]:
    if state.get("answer_quality_grade") == "yes":
        return "finalize_response"
    if state.get("iteration", 0) >= state.get("max_iterations", 2):
        return "finalize_response"
    return "retry_generation"


@lru_cache(maxsize=1)
def build_agent_mermaid() -> str:
    """Render the compiled orchestrator graph as Mermaid text."""
    graph = build_agent_graph()
    return graph.get_graph().draw_mermaid()
