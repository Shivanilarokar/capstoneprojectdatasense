from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal


def _looks_like_date(value: str) -> bool:
    if len(value) != 10:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _is_currency_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ("usd", "value", "damage", "amount", "total"))


def _is_percentage_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ("pct", "percent", "percentage", "rate", "ratio"))


def format_scalar(key: str, value):
    if value is None:
        return "null"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        if _is_percentage_key(key):
            percent_value = float(value) * 100 if abs(float(value)) <= 1 else float(value)
            return f"{percent_value:,.1f}%".rstrip("0").rstrip(".") + ("" if str(percent_value).endswith(".0") else "")
        if _is_currency_key(key):
            rounded = round(float(value))
            return f"${rounded:,.0f}"
        if isinstance(value, float):
            return f"{value:,.2f}".rstrip("0").rstrip(".")
        return f"{value:,}"
    text = str(value)
    if _looks_like_date(text):
        return text
    return text


def format_rows_for_display(rows: list[dict]) -> list[dict]:
    return [
        {key: format_scalar(key, value) for key, value in row.items()}
        for row in rows
    ]


def build_evidence_lines(rows: list[dict], *, limit: int = 5) -> list[str]:
    if not rows:
        return ["No matching rows returned."]

    evidence_lines: list[str] = []
    for idx, row in enumerate(rows[:limit], start=1):
        values = list(row.values())
        if not values:
            evidence_lines.append(f"{idx}. (empty row)")
            continue
        rendered = " | ".join(str(value) for value in values[:3])
        evidence_lines.append(f"{idx}. {rendered}")
    return evidence_lines


def summarize_methodology(*, route: str, sql: str, row_count: int) -> str:
    route_label = {
        "weather": "NOAA storm events",
        "trade": "UN Comtrade trade flows",
        "fda": "FDA warning letters",
        "sanctions": "OFAC SDN entities",
        "cross_source": "FDA warning letters joined to OFAC SDN entities",
    }.get(route, "approved PostgreSQL source tables")
    lowered_sql = sql.lower()
    actions: list[str] = []
    if " join " in lowered_sql:
        actions.append("joined")
    if "group by" in lowered_sql:
        actions.append("aggregated")
    if "count(" in lowered_sql and "aggregated" not in actions:
        actions.append("counted")
    if "order by" in lowered_sql:
        actions.append("ranked")
    if not actions:
        actions.append("queried")

    action_text = ", ".join(actions[:-1]) + (" and " if len(actions) > 1 else "") + actions[-1]
    return (
        f"Executed a read-only PostgreSQL query over {route_label}, {action_text} the matching records, "
        f"returned {row_count} row{'' if row_count == 1 else 's'}, and summarized the validated results."
    )


def render_answer_first(
    *,
    question: str,
    answer: str,
    methodology: str,
    evidence_lines: list[str],
) -> str:
    blocks = [
        "Question",
        question,
        "",
        "Answer",
        answer,
        "",
        "How It Was Computed",
        methodology,
        "",
        "Evidence",
        *evidence_lines,
    ]
    return "\n".join(blocks).strip()


