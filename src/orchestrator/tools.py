"""LangChain tool wrappers for deterministic route pipelines."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from config import AppConfig
from ingestion.cli import run_ingestion


def build_router_model(model_name: str, *, api_key: str | None = None, temperature: float = 0):
    """Build the OpenAI router model when `langchain-openai` is available."""
    try:
        from langchain_openai import ChatOpenAI
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised through integration paths
        raise RuntimeError(
            "langchain-openai is required to build the router model. "
            "Install project dependencies to enable the OpenAI-backed LangGraph router."
        ) from exc

    return ChatOpenAI(model=model_name, api_key=api_key, temperature=temperature)


def build_route_tools(
    settings: AppConfig,
    *,
    user_id: str,
    options: Any,
) -> dict[str, Any]:
    """Build bound LangChain tools for the current request context."""

    @tool("pageindex")
    def pageindex_tool(question: str) -> dict[str, Any]:
        """Use SEC 10-K sections and PageIndex retrieval for filing and disclosure questions."""
        from .agent import _run_pageindex_route

        return _run_pageindex_route(settings, question, options)

    @tool("sanctions")
    def sanctions_tool(question: str) -> dict[str, Any]:
        """Use deterministic OFAC/BIS screening for sanctions and entity-list questions."""
        from .agent import _run_sanctions_route

        return _run_sanctions_route(settings, question, user_id)

    @tool("nlsql")
    def nlsql_tool(question: str) -> dict[str, Any]:
        """Use PostgreSQL analytics for counts, rankings, aggregations, and exact tabular answers."""
        from .agent import _run_nlsql_route

        return _run_nlsql_route(settings, question)

    @tool("graphrag")
    def graphrag_tool(question: str, graph_routes_hint: list[str] | None = None) -> dict[str, Any]:
        """Use graph retrieval for dependency, cascade, multi-tier, and exposure questions."""
        from .agent import _run_graphrag_route

        return _run_graphrag_route(
            settings,
            question,
            options,
            user_id=user_id,
            graph_routes_hint=graph_routes_hint,
        )

    @tool("ingestion")
    def ingestion_tool(
        source: str,
        tenant_id: str = "default",
        init_schema: bool = False,
        batch_size: int = 1000,
    ) -> dict[str, Any]:
        """Load local source files into PostgreSQL for the selected tenant."""
        return run_ingestion(
            source=source,
            tenant_id=tenant_id,
            init_schema=init_schema,
            batch_size=batch_size,
        )

    return {
        "pageindex": pageindex_tool,
        "sanctions": sanctions_tool,
        "nlsql": nlsql_tool,
        "graphrag": graphrag_tool,
        "ingestion": ingestion_tool,
    }
