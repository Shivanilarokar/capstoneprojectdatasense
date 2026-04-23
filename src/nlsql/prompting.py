from __future__ import annotations


def build_sql_generation_prompt(*, question: str, schema_text: str) -> str:
    return f"""
You are a PostgreSQL analytics SQL generator.
Use only approved tables from this schema:
{schema_text}

Return strict JSON with keys:
- reasoning
- tables
- sql
- ambiguity

Only generate one read-only PostgreSQL query.
Use psycopg named parameters, including the literal placeholder %(tenant_id)s when tenant filtering is required.
If a referenced table contains tenant_id, the SQL must filter that table by tenant_id.
For joins, include tenant_id filters for each tenant-scoped table alias.

Question:
{question}
""".strip()


def build_sql_repair_prompt(
    *,
    question: str,
    schema_text: str,
    bad_sql: str,
    db_error: str,
) -> str:
    return f"""
Repair the PostgreSQL query using the same schema and safety rules.
The repaired SQL must keep or add required tenant filters using %(tenant_id)s.

Schema:
{schema_text}

Question:
{question}

Failed SQL:
{bad_sql}

Database error:
{db_error}
""".strip()


def build_answer_prompt(*, question: str, sql: str, rows: list[dict]) -> str:
    return f"""
Answer the user's question from the SQL results only.

Question:
{question}

SQL:
{sql}

Rows:
{rows}
""".strip()
