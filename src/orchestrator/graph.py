"""Graph builder for the LangGraph competition orchestrator."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from .models import OrchestratorState


def build_agent_graph(
    *,
    route_question_node: Any | None = None,
    route_mode: Any | None = None,
    run_single_route_node: Any | None = None,
    plan_fullstack_node: Any | None = None,
    run_next_fullstack_route_node: Any | None = None,
    fullstack_loop: Any | None = None,
    finalize_response_node: Any | None = None,
):
    """Compile the central LangGraph workflow for request orchestration."""
    if route_question_node is None:
        from . import agent as agent_module

        route_question_node = agent_module._route_question_node
        route_mode = agent_module._route_mode
        run_single_route_node = agent_module._run_single_route_node
        plan_fullstack_node = agent_module._plan_fullstack_node
        run_next_fullstack_route_node = agent_module._run_next_fullstack_route_node
        fullstack_loop = agent_module._fullstack_loop
        finalize_response_node = agent_module._finalize_response_node

    workflow = StateGraph(OrchestratorState)
    workflow.add_node("route_question", route_question_node)
    workflow.add_node("run_single_route", run_single_route_node)
    workflow.add_node("plan_fullstack", plan_fullstack_node)
    workflow.add_node("run_next_fullstack_route", run_next_fullstack_route_node)
    workflow.add_node("finalize_response", finalize_response_node)

    workflow.add_edge(START, "route_question")
    workflow.add_conditional_edges(
        "route_question",
        route_mode,
        {
            "run_single_route": "run_single_route",
            "plan_fullstack": "plan_fullstack",
        },
    )
    workflow.add_edge("run_single_route", "finalize_response")
    workflow.add_conditional_edges(
        "plan_fullstack",
        fullstack_loop,
        {
            "run_next_fullstack_route": "run_next_fullstack_route",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_conditional_edges(
        "run_next_fullstack_route",
        fullstack_loop,
        {
            "run_next_fullstack_route": "run_next_fullstack_route",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_edge("finalize_response", END)
    return workflow.compile()
