from __future__ import annotations

from datetime import date, datetime


def _format_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return str(value)


def _render_route_lines(route_result: dict, *, max_lines: int = 3) -> list[str]:
    route = str(route_result.get("route", "unknown"))
    lines: list[str] = []

    if "error" in route_result:
        return [f"- {route}: {route_result['error']}"]

    list_fields = [(key, value) for key, value in route_result.items() if isinstance(value, list)]
    scalar_fields = [(key, value) for key, value in route_result.items() if key != "route" and not isinstance(value, list)]

    if not list_fields and not scalar_fields:
        return [f"- {route}: no evidence"]

    summary_bits = [f"{key}={len(value)}" for key, value in list_fields]
    if scalar_fields:
        summary_bits.extend(
            f"{key}={_format_scalar(value)}"
            for key, value in scalar_fields
            if value is not None
        )
    lines.append(f"- {route}: " + (", ".join(summary_bits) if summary_bits else "no evidence"))

    preview_count = 0
    for key, values in list_fields:
        if not values:
            continue
        first = values[0]
        if isinstance(first, dict):
            preview = " | ".join(_format_scalar(value) for value in list(first.values())[:4])
        else:
            preview = _format_scalar(first)
        lines.append(f"  {key}: {preview}")
        preview_count += 1
        if preview_count >= max_lines:
            break

    return lines


def render_graph_output(result: dict) -> str:
    question = str(result.get("question", ""))
    answer = str(result.get("answer", ""))
    routes = [str(route) for route in result.get("routes", [])]
    evidence = list(result.get("evidence", []) or [])

    route_lines = [f"{idx}. {route}" for idx, route in enumerate(routes, start=1)] or [
        "No retrieval routes were selected."
    ]

    evidence_lines: list[str] = []
    for route_result in evidence:
        evidence_lines.extend(_render_route_lines(route_result))
    if not evidence_lines:
        evidence_lines = ["No route evidence returned."]

    blocks = [
        "Question",
        question,
        "",
        "Answer",
        answer,
        "",
        "Routes Used",
        *route_lines,
        "",
        "Evidence",
        *evidence_lines,
    ]
    return "\n".join(blocks).strip()


