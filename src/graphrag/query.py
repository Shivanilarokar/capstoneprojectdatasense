"""Graph RAG query execution without orchestration graph dependencies."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Generation.generation import LLMConfig, chat_json, chat_text
from config import AppConfig

from .neo4j_store import Neo4jStore
from .retrieval.retrievers import retrieve_route
from .retrieval.router import query_terms, route_question

ALLOWED_ROUTES = ["financial", "sanctions", "trade", "hazard", "regulatory", "cascade"]


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON line to an audit file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _default_answer(question: str, routed_results: list[dict[str, Any]]) -> str:
    """Fallback answer format when LLM synthesis is disabled/unavailable."""
    lines = [f"Question: {question}", "", "Graph evidence summary:"]
    for item in routed_results:
        route = item.get("route")
        lines.append(f"- Route `{route}`:")
        for key, value in item.items():
            if key == "route":
                continue
            if isinstance(value, list):
                lines.append(f"  {key}: {len(value)} records")
            elif isinstance(value, dict):
                lines.append(f"  {key}: {json.dumps(value)}")
            else:
                lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _llm_route(question: str, llm: LLMConfig) -> list[str]:
    """LLM-assisted route selection inside GraphRAG execution stage."""
    prompt = f"""
You are a query router for a supply-chain Graph RAG system.
Given a user question, choose one or more routes from:
{ALLOWED_ROUTES}

Routing intent:
- financial: SEC filing risks, supplier disclosures, going concern
- sanctions: OFAC/BIS entity screening, alias matching
- trade: Comtrade flows, commodity concentration, import/export trends
- hazard: NOAA severe weather and location-based hazard exposure
- regulatory: FDA warning letters/import alerts/compliance risk
- cascade: multi-tier dependency/cascading failure exposure

Return strict JSON:
{{
  "routes": ["financial", "sanctions"]
}}

Question:
{question}
"""
    parsed = chat_json(llm, prompt, temperature=0)
    routes = parsed.get("routes", [])
    if not isinstance(routes, list):
        routes = []
    selected: list[str] = []
    for route in routes:
        if not isinstance(route, str):
            continue
        route_name = route.strip().lower()
        if route_name in ALLOWED_ROUTES and route_name not in selected:
            selected.append(route_name)
    return selected


def plan_graph_routes(
    settings: AppConfig,
    question: str,
    *,
    forced_routes: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Plan GraphRAG routes and lexical terms for retrieval queries."""
    terms = query_terms(question)

    selected: list[str] = []
    if forced_routes:
        for route in forced_routes:
            route_name = str(route).strip().lower()
            if route_name in ALLOWED_ROUTES and route_name not in selected:
                selected.append(route_name)
    if not selected and settings.openai_api_key:
        llm = LLMConfig(api_key=settings.openai_api_key, model=settings.openai_model)
        try:
            selected = _llm_route(question, llm)
        except Exception:
            selected = []
    if not selected:
        selected = route_question(question)
    return selected, terms


def _synthesize_answer(
    question: str,
    routes: list[str],
    evidence: list[dict[str, Any]],
    llm: LLMConfig,
) -> str:
    """LLM synthesis for route-evidence graph output."""
    evidence_payload = json.dumps(evidence, ensure_ascii=False)[:70000]
    prompt = f"""
You are SupplyChainNexus Graph RAG assistant.
Answer only from provided graph evidence. If insufficient evidence exists, say exactly what is missing.
If `trade` route exists, explicitly disclose Comtrade freshness.
For sanctions-related questions, be strict and avoid guessing.

Question:
{question}

Routes:
{routes}

Evidence:
{evidence_payload}
"""
    return chat_text(llm, prompt, temperature=0)


def run_graph_query(
    settings: AppConfig,
    question: str,
    *,
    max_results: int = 20,
    use_llm_synthesis: bool = True,
    user_id: str = "system",
    forced_routes: list[str] | None = None,
) -> dict[str, Any]:
    """Execute Graph RAG retrieval + optional synthesis as a plain pipeline."""
    tenant_id = settings.graph_tenant_id
    routes, terms = plan_graph_routes(settings, question, forced_routes=forced_routes)

    store = Neo4jStore(settings)
    try:
        evidence: list[dict[str, Any]] = []
        for route in routes:
            evidence.append(
                retrieve_route(
                    store=store,
                    route=route,
                    tenant_id=tenant_id,
                    terms=terms,
                    limit=max_results,
                )
            )
    finally:
        store.close()

    audit_log_path = str(settings.sanctions_audit_log)
    if "sanctions" in routes:
        sanctions_result = next((row for row in evidence if row.get("route") == "sanctions"), {})
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "question": question,
            "terms_checked": terms,
            "routes": routes,
            "result_counts": {
                "sanctions_list": len(sanctions_result.get("sanctions_list", [])),
                "exact_entity_matches": len(sanctions_result.get("exact_entity_matches", [])),
            },
        }
        _append_jsonl(settings.sanctions_audit_log, payload)

    if use_llm_synthesis and settings.openai_api_key:
        llm = LLMConfig(api_key=settings.openai_api_key, model=settings.openai_model)
        try:
            answer = _synthesize_answer(question, routes, evidence, llm)
        except Exception:
            answer = _default_answer(question, evidence)
    else:
        answer = _default_answer(question, evidence)

    return {
        "question": question,
        "tenant_id": tenant_id,
        "routes": routes,
        "terms": terms,
        "answer": answer,
        "evidence": evidence,
        "audit_log_path": audit_log_path,
    }
