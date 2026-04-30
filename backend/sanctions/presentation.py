from __future__ import annotations


def _render_match_lines(matches: list[dict]) -> list[str]:
    if not matches:
        return ["None"]
    lines: list[str] = []
    for idx, match in enumerate(matches[:5], start=1):
        program = match.get("sanctions_programs") or "unspecified"
        score = float(match.get("score", 0.0))
        lines.append(
            f"{idx}. {match.get('entity_name', '')} -> {match.get('matched_name', '')} "
            f"| {match.get('match_type', '')} | score={score:.2f} | program={program}"
        )
    return lines


def render_sanctions_output(result: dict) -> str:
    question = str(result.get("question", ""))
    answer = str(result.get("answer", ""))
    evidence = result.get("evidence", {}) or {}
    freshness = result.get("freshness", {}) or {}
    warnings = result.get("warnings", []) or []

    lines = [
        "Question",
        question,
        "",
        "Answer",
        answer,
        "",
        "Matched Entities",
        *_render_match_lines(list(evidence.get("matches", []))),
        "",
        "Freshness",
        f"Latest loaded at: {freshness.get('latest_loaded_at') or 'unavailable'}",
    ]

    if warnings:
        lines.extend(
            [
                "",
                "Warnings",
                *[str(warning) for warning in warnings],
            ]
        )

    return "\n".join(lines).strip()


