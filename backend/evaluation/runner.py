from __future__ import annotations

from typing import Any

from backend.config import AppConfig
from backend.orchestrator.router import AgenticOptions, run_agentic_query

from .benchmarks import BENCHMARKS


def _fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _completed_routes(result: dict[str, Any]) -> list[str]:
    routes = result.get("completed_routes") or result.get("routes_executed") or []
    return list(routes)


def _unique_match_precision(route_result: dict[str, Any]) -> float:
    evidence = route_result.get("evidence", {})
    matches = evidence.get("matches", [])
    if not matches:
        return 0.0
    unique_names = {str(match.get("matched_name", "")).strip().lower() for match in matches if match.get("matched_name")}
    return _fraction(len(unique_names), len(matches))


def _graph_completeness(result: dict[str, Any]) -> float:
    graphrag = (result.get("route_results") or {}).get("graphrag", {})
    evidence = graphrag.get("evidence", {})
    routes = evidence.get("routes", [])
    rows = evidence.get("results", [])
    if not routes:
        return 0.0
    populated = sum(1 for row in rows if row)
    return _fraction(populated, len(routes))


def _geographic_signal(result: dict[str, Any]) -> float:
    answer = str(result.get("answer", "")).lower()
    if any(token in answer for token in ("state", "county", "country", "hazard zone")):
        return 1.0
    route_results = result.get("route_results") or {}
    for route in ("nlsql", "graphrag"):
        evidence = (route_results.get(route) or {}).get("evidence", {})
        rows = evidence.get("rows") or evidence.get("results") or []
        serialized = str(rows).lower()
        if any(token in serialized for token in ("state", "county", "country", "lat", "lon", "hazard_zone")):
            return 1.0
    return 0.0


def build_ablation_report(records: list[dict[str, Any]]) -> dict[str, float]:
    total = len(records)
    if total <= 0:
        return {
            "A0_single_route_baseline": 0.0,
            "A1_router_enabled": 0.0,
            "A2_structured_tooling": 0.0,
            "A3_graph_augmented": 0.0,
            "A4_sanctions_resolution": 0.0,
            "A5_full_orchestrator": 0.0,
        }

    router_enabled = 0
    structured = 0
    graph_augmented = 0
    sanctions_resolution = 0
    full_orchestrator = 0
    single_route = 0

    for record in records:
        result = record["result"]
        completed = _completed_routes(result)
        if completed:
            router_enabled += 1
        if any(route in completed for route in ("nlsql", "pageindex")):
            structured += 1
        if "graphrag" in completed:
            graph_augmented += 1
        if "sanctions" in completed:
            sanctions_resolution += 1
        if len(completed) >= 2:
            full_orchestrator += 1
        if len(completed) == 1:
            single_route += 1

    return {
        "A0_single_route_baseline": _fraction(single_route, total),
        "A1_router_enabled": _fraction(router_enabled, total),
        "A2_structured_tooling": _fraction(structured, total),
        "A3_graph_augmented": _fraction(graph_augmented, total),
        "A4_sanctions_resolution": _fraction(sanctions_resolution, total),
        "A5_full_orchestrator": _fraction(full_orchestrator, total),
    }


def score_run(records: list[dict[str, Any]]) -> dict[str, float]:
    total = len(records)
    route_hits = 0
    provenance_hits = 0
    freshness_hits = 0
    cross_source_total = 0
    cross_source_hits = 0
    sanctions_total = 0
    sanctions_hits = 0
    sanctions_precision_total = 0
    sanctions_precision_sum = 0.0
    cascade_total = 0
    cascade_hits = 0
    graph_total = 0
    graph_sum = 0.0
    geography_total = 0
    geography_sum = 0.0

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
            sanctions_precision_total += 1
            sanctions_precision_sum += _unique_match_precision(sanctions_result)
        if "cascade" in tags:
            cascade_total += 1
            if "graphrag" in _completed_routes(result) and str(result.get("answer", "")).strip():
                cascade_hits += 1
        if "graph" in tags or "cascade" in tags:
            graph_total += 1
            graph_sum += _graph_completeness(result)
        if "hazard" in tags:
            geography_total += 1
            geography_sum += _geographic_signal(result)

    return {
        "route_accuracy": _fraction(route_hits, total),
        "provenance_coverage": _fraction(provenance_hits, total),
        "freshness_disclosure_rate": _fraction(freshness_hits, total),
        "cross_source_completion_rate": _fraction(cross_source_hits, cross_source_total),
        "sanctions_decision_explainability": _fraction(sanctions_hits, sanctions_total),
        "cascading_risk_answer_success": _fraction(cascade_hits, cascade_total),
        "entity_match_precision": _fraction(int(sanctions_precision_sum * 1000), sanctions_precision_total * 1000),
        "graph_traversal_completeness": _fraction(int(graph_sum * 1000), graph_total * 1000),
        "geographic_accuracy": _fraction(int(geography_sum * 1000), geography_total * 1000),
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
        "ablations": build_ablation_report(records),
    }

