from __future__ import annotations

import re

from .models import ValidationResult


_BANNED = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|copy|call|do)\b", re.I)
_COMMENT = re.compile(r"(--|/\*)")
_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)", re.I)
_CTE_NAME = re.compile(r"(?:\bwith|,)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\b", re.I)


def validate_generated_sql(
    sql: str,
    *,
    allowed_tables: set[str],
    tenant_tables: set[str],
) -> ValidationResult:
    text = sql.strip()
    lowered = text.lower()

    if not text:
        return ValidationResult(ok=False, reason="Generated SQL cannot be blank.")
    if ";" in text.rstrip(";"):
        return ValidationResult(ok=False, reason="Only one SQL statement is allowed.")
    if _COMMENT.search(text):
        return ValidationResult(ok=False, reason="SQL comments are not allowed.")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return ValidationResult(ok=False, reason="Only SELECT queries are allowed.")
    if _BANNED.search(text):
        return ValidationResult(ok=False, reason="Only read-only SQL is allowed.")

    cte_names = {match.group(1) for match in _CTE_NAME.finditer(text)}
    tables = {
        match.group(1).split(".")[-1]
        for match in _TABLE_REF.finditer(text)
        if match.group(1).split(".")[-1] not in cte_names
    }
    if not tables:
        return ValidationResult(ok=False, reason="SQL must reference approved tables.")
    if not tables.issubset(allowed_tables):
        return ValidationResult(ok=False, reason="SQL may only use approved tables.")

    for table in tables & tenant_tables:
        if "tenant_id" not in lowered:
            return ValidationResult(ok=False, reason=f"SQL must filter {table} by tenant_id.")

    return ValidationResult(ok=True)
