from __future__ import annotations

import re
from typing import Any


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "unknown"


def _node_id(kind: str, label: str) -> str:
    return f"{kind}:{_slug(label)}"


def _empty_graph(*, query_id: str = "", mode: str = "answer") -> dict[str, Any]:
    return {
        "query_id": query_id,
        "mode": mode,
        "nodes": [],
        "edges": [],
        "stats": {
            "node_count": 0,
            "edge_count": 0,
            "routes": [],
        },
    }


def _append_node(nodes: dict[str, dict[str, Any]], *, kind: str, label: str, route: str, subtitle: str = "") -> str | None:
    normalized = str(label or "").strip()
    if not normalized:
        return None
    node_key = _node_id(kind, normalized)
    if node_key not in nodes:
        nodes[node_key] = {
            "data": {
                "id": node_key,
                "label": normalized,
                "kind": kind,
                "route": route,
                "subtitle": subtitle,
            }
        }
    return node_key


def _append_edge(
    edges: dict[str, dict[str, Any]],
    *,
    source: str | None,
    target: str | None,
    label: str,
    route: str,
    kind: str,
) -> None:
    if not source or not target:
        return
    edge_key = f"{source}->{target}:{kind}:{_slug(label)}"
    if edge_key not in edges:
        edges[edge_key] = {
            "data": {
                "id": edge_key,
                "source": source,
                "target": target,
                "label": label,
                "route": route,
                "kind": kind,
            }
        }


def _build_from_cascade(route_result: dict[str, Any], nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> None:
    for row in route_result.get("multi_tier_paths", []) or []:
        company = _append_node(nodes, kind="company", label=str(row.get("company", "")), route="cascade", subtitle=str(row.get("ticker", "")))
        tier1 = _append_node(nodes, kind="supplier", label=str(row.get("tier1_supplier", "")), route="cascade")
        tier2 = _append_node(nodes, kind="supplier", label=str(row.get("tier2_supplier", "")), route="cascade")
        component = _append_node(nodes, kind="component", label=str(row.get("component", "")), route="cascade")
        material = _append_node(nodes, kind="material", label=str(row.get("raw_material", "")), route="cascade")
        country = _append_node(nodes, kind="country", label=str(row.get("source_country", "")), route="cascade")
        hazard = _append_node(nodes, kind="hazard", label=str(row.get("hazard_zone", "")), route="cascade")
        sanctions_status = _append_node(
            nodes,
            kind="status",
            label=str(row.get("sanctions_status", "")),
            route="cascade",
            subtitle=str(row.get("sanctions_match_type", "")),
        )

        _append_edge(edges, source=company, target=tier1, label="tier 1", route="cascade", kind="tier")
        _append_edge(edges, source=tier1, target=tier2, label="tier 2", route="cascade", kind="tier")
        _append_edge(edges, source=tier2, target=component, label="component", route="cascade", kind="component")
        _append_edge(edges, source=component, target=material, label="material", route="cascade", kind="material")
        _append_edge(edges, source=material, target=country, label="source", route="cascade", kind="source")
        _append_edge(edges, source=country, target=hazard, label="hazard", route="cascade", kind="hazard")
        _append_edge(edges, source=tier2, target=sanctions_status, label="sanctions", route="cascade", kind="status")


def _build_from_sanctions_matches(matches: list[dict[str, Any]], nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> None:
    for row in matches or []:
        supplier_label = str(row.get("supplier_name") or row.get("supplier") or "").strip()
        target_label = str(row.get("matched_name") or row.get("sanctioned_entity") or "").strip()
        supplier = _append_node(nodes, kind="supplier", label=supplier_label, route="sanctions")
        target = _append_node(nodes, kind="sanction_entity", label=target_label, route="sanctions", subtitle=str(row.get("source_list", "")))
        _append_edge(
            edges,
            source=supplier,
            target=target,
            label="matched",
            route="sanctions",
            kind=str(row.get("match_type", "match")),
        )


def _build_from_graphrag_results(results: list[dict[str, Any]], nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> list[str]:
    routes: list[str] = []
    for route_result in results or []:
        route = str(route_result.get("route", "")).strip().lower()
        if not route:
            continue
        if route not in routes:
            routes.append(route)

        if route == "cascade":
            _build_from_cascade(route_result, nodes, edges)
            continue

        if route == "sanctions":
            _build_from_sanctions_matches(route_result.get("exact_entity_matches", []), nodes, edges)
            for row in route_result.get("sanctions_list", []) or []:
                _append_node(
                    nodes,
                    kind="sanction_entity",
                    label=str(row.get("name", "")),
                    route="sanctions",
                    subtitle=str(row.get("source_list", "")),
                )
            continue

        if route == "regulatory":
            for row in route_result.get("quality_regulatory_actions", []) or []:
                company = _append_node(nodes, kind="company", label=str(row.get("company", "")), route="regulatory")
                action_label = str(row.get("action_type", "")) or "Regulatory action"
                action = _append_node(
                    nodes,
                    kind="regulatory_action",
                    label=action_label,
                    route="regulatory",
                    subtitle=str(row.get("issue_date", "")),
                )
                _append_edge(edges, source=action, target=company, label="targets", route="regulatory", kind="regulatory")
            continue

        if route == "hazard":
            for row in route_result.get("hazard_zones", []) or []:
                country = _append_node(nodes, kind="country", label=str(row.get("country", "")), route="hazard")
                zone = _append_node(
                    nodes,
                    kind="hazard",
                    label=":".join(part for part in [str(row.get("state", "")), str(row.get("county", ""))] if part).strip(":"),
                    route="hazard",
                )
                _append_edge(edges, source=country, target=zone, label="hazard zone", route="hazard", kind="hazard")
            continue

        if route == "trade":
            for row in route_result.get("commodity_trade_flows", []) or []:
                reporter = _append_node(nodes, kind="country", label=str(row.get("reporter", "")), route="trade")
                partner = _append_node(nodes, kind="country", label=str(row.get("partner", "")), route="trade")
                commodity = _append_node(nodes, kind="commodity", label=str(row.get("commodity_desc", "")), route="trade")
                _append_edge(edges, source=reporter, target=commodity, label=str(row.get("flow", "trade")), route="trade", kind="trade")
                _append_edge(edges, source=commodity, target=partner, label="partner", route="trade", kind="trade")
            continue

        if route == "financial":
            for row in route_result.get("financial_health", []) or []:
                company = _append_node(nodes, kind="company", label=str(row.get("company", "")), route="financial", subtitle=str(row.get("ticker", "")))
                filing = _append_node(
                    nodes,
                    kind="filing_section",
                    label=str(row.get("item_code", "")) or "filing",
                    route="financial",
                    subtitle=str(row.get("filing_date", "")),
                )
                _append_edge(edges, source=company, target=filing, label="discloses", route="financial", kind="filing")
    return routes


def build_answer_graph(result: dict[str, Any]) -> dict[str, Any]:
    query_id = str(result.get("query_id", ""))
    route_results = result.get("filtered_route_results") or result.get("route_results") or {}
    if not isinstance(route_results, dict) or not route_results:
        return _empty_graph(query_id=query_id, mode="answer")

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    routes: list[str] = []

    graphrag_result = route_results.get("graphrag", {})
    graphrag_evidence = ((graphrag_result or {}).get("evidence") or {}).get("results", [])
    if isinstance(graphrag_evidence, list):
        routes.extend(_build_from_graphrag_results(graphrag_evidence, nodes, edges))

    sanctions_matches = ((route_results.get("sanctions", {}) or {}).get("evidence") or {}).get("matches", [])
    if sanctions_matches:
        _build_from_sanctions_matches(sanctions_matches, nodes, edges)
        if "sanctions" not in routes:
            routes.append("sanctions")

    graph = {
        "query_id": query_id,
        "mode": "answer",
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "routes": routes,
        },
    }
    return graph


def build_graph_explorer() -> dict[str, Any]:
    return _empty_graph(mode="explorer")
