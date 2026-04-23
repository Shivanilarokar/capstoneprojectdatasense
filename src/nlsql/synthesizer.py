from __future__ import annotations


def synthesize_nlsql_answer(question: str, plan: dict, rows: list[dict]) -> str:
    if plan["query_type"] == "trade_top_exporters":
        lines = [f"Question: {question}", "", "Top exporters:"]
        for idx, row in enumerate(rows, start=1):
            lines.append(f"{idx}. {row['reporter_desc']}: {row['total_value']}")
        return "\n".join(lines)
    return "NL-SQL route could not answer the question with the current safe query templates."
