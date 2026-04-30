from __future__ import annotations

from backend.config import AppConfig
from backend.app.services.graph_service import build_answer_graph
from backend.orchestrator.router import AgenticOptions, run_agentic_query


def ask_supplychainnexus(
    settings: AppConfig,
    question: str,
    user_id: str,
    roles: tuple[str, ...],
) -> dict:
    result = run_agentic_query(
        settings=settings,
        question=question,
        user_id=user_id,
        options=AgenticOptions(user_roles=roles),
    )
    result["answer_graph"] = build_answer_graph(result)
    return result
