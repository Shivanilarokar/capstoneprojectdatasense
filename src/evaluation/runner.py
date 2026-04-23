from __future__ import annotations

from typing import Any

from config import AppConfig
from orchestrator.agent import AgenticOptions, run_agentic_query

from .benchmarks import BENCHMARKS


def _fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _completed_routes(result: dict[str, Any]) -> list[str]:
    routes = result.get("completed_routes") or result.get("routes_executed") or []
    return list(routes)


def score_run(records: list[dict[str, Any]]) -> dict[str, float]:
    total = len(records)
    route_hits = 0
    provenance_hits = 0
    freshness_hits = 0
    cross_source_total = 0
    cross_source_hits = 0
    sanctions_total = 0
    sanctions_hits = 0
    cascade_total = 0
    cascade_hits = 0

    for record in records:
        benchmark = record["benchmark"]
        result = record["result"]
        tags = set(benchmark.get("tags", []))
        if benchmark.get("expected_route") == result.get("selected_pipeline"):
            route_hits += 1
        if result.get("provenance"):
            provenance_hits += 1
        if result.get("freshness"):
            freshness_hits += 1
        if "cross_source" in tags:
            cross_source_total += 1
            if len(_completed_routes(result)) >= 2:
                cross_source_hits += 1
        if "sanctions" in tags:
            sanctions_total += 1
            sanctions_result = (result.get("route_results") or {}).get("sanctions", {})
            sanctions_evidence = sanctions_result.get("evidence", {})
            if sanctions_evidence.get("matches") or sanctions_result.get("warnings") == []:
                sanctions_hits += 1
        if "cascade" in tags:
            cascade_total += 1
            if "graphrag" in _completed_routes(result) and str(result.get("answer", "")).strip():
                cascade_hits += 1

    return {
        "route_accuracy": _fraction(route_hits, total),
        "provenance_coverage": _fraction(provenance_hits, total),
        "freshness_disclosure_rate": _fraction(freshness_hits, total),
        "cross_source_completion_rate": _fraction(cross_source_hits, cross_source_total),
        "sanctions_decision_explainability": _fraction(sanctions_hits, sanctions_total),
        "cascading_risk_answer_success": _fraction(cascade_hits, cascade_total),
    }


def run_benchmarks(
    settings: AppConfig,
    *,
    benchmarks: list[dict[str, Any]] | None = None,
    limit: int | None = None,
    options: AgenticOptions | None = None,
) -> dict[str, Any]:
    chosen_benchmarks = list(benchmarks or BENCHMARKS)
    if limit is not None:
        chosen_benchmarks = chosen_benchmarks[:limit]

    records: list[dict[str, Any]] = []
    for benchmark in chosen_benchmarks:
        result = run_agentic_query(
            settings=settings,
            question=benchmark["question"],
            options=options or AgenticOptions(),
        )
        records.append({"benchmark": benchmark, "result": result})

    return {
        "tenant_id": settings.graph_tenant_id,
        "benchmark_count": len(chosen_benchmarks),
        "records": records,
        "summary": score_run(records),
    }
