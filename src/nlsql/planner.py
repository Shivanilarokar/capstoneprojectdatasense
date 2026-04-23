from __future__ import annotations

import re


def heuristic_nlsql_plan(question: str) -> dict:
    text = question.lower()
    year_match = re.search(r"(20\d{2})", text)
    limit_match = re.search(r"top\s+(\d+)", text)
    if "top" in text and ("export" in text or "exporting" in text):
        return {
            "query_type": "trade_top_exporters",
            "year": int(year_match.group(1)) if year_match else None,
            "limit": int(limit_match.group(1)) if limit_match else 5,
        }
    return {
        "query_type": "unsupported",
        "reason": "Question does not match current safe NL-SQL templates.",
    }
