"""Shared result-envelope helpers for competition routes."""

from __future__ import annotations

from typing import Any


def make_result_envelope(
    *,
    question: str,
    route: str,
    answer: str,
    status: str = "ok",
    evidence: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    freshness: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    debug: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "status": status,
        "question": question,
        "route": route,
        "answer": answer,
        "evidence": evidence or {},
        "provenance": provenance or {},
        "freshness": freshness or {},
        "warnings": warnings or [],
        "debug": debug or {},
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    return payload


def normalize_nlsql_result(question: str, tenant_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    execution = raw.get("execution") or {}
    validation = raw.get("validation") or {}
    if execution.get("error"):
        warnings.append(str(execution["error"]))
    if validation.get("ok") is False and validation.get("reason"):
        warnings.append(str(validation["reason"]))

    return make_result_envelope(
        question=question,
        route="nlsql",
        answer=str(raw.get("answer", "")),
        evidence={
            "rows": raw.get("rows", []),
            "generation": raw.get("generation", {}),
            "validation": validation,
        },
        provenance={
            "source_tables": raw.get("schema_tables", []),
            "sql": execution.get("sql", ""),
            "params": execution.get("params", {}),
        },
        freshness={
            "note": "Structured analytics reflect the current PostgreSQL source tables for the selected tenant."
        },
        warnings=warnings,
        debug={
            "execution": execution,
            "row_count": execution.get("row_count", len(raw.get("rows", []))),
        },
        tenant_id=tenant_id,
    )


def normalize_graphrag_result(question: str, tenant_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    routes = raw.get("routes", [])
    warnings: list[str] = []
    if "trade" in routes:
        warnings.append("Trade evidence may lag source systems because Comtrade updates are periodic.")

    return make_result_envelope(
        question=question,
        route="graphrag",
        answer=str(raw.get("answer", "")),
        evidence={
            "routes": routes,
            "results": raw.get("evidence", []),
        },
        provenance={
            "graph_routes": routes,
            "terms": raw.get("terms", []),
            "audit_log_path": raw.get("audit_log_path", ""),
        },
        freshness={
            "note": "Graph evidence reflects the current Neo4j topology built from the ingested datasets."
        },
        warnings=warnings,
        debug={"raw": raw},
        tenant_id=tenant_id,
    )


def normalize_pageindex_result(question: str, tenant_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    qa_result = raw.get("qa_result") or {}
    summary = raw.get("summary") or {}
    return make_result_envelope(
        question=question,
        route="pageindex",
        answer=str(raw.get("answer", "")),
        evidence={
            "qa_result": qa_result,
            "summary": summary,
        },
        provenance={
            "qa_result_file": summary.get("qa_result_file"),
            "doc_registry_file": summary.get("doc_registry_file"),
            "run_summary_file": summary.get("run_summary_file"),
        },
        freshness={
            "note": "PageIndex evidence reflects the currently extracted SEC filing sections in the local workspace."
        },
        warnings=[],
        debug={"summary": summary},
        tenant_id=tenant_id,
    )


