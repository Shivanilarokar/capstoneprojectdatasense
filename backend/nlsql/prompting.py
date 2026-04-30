from __future__ import annotations

from .examples import render_route_examples, render_route_guidance


def build_sql_generation_prompt(
    *,
    question: str,
    schema_text: str,
    route: str,
    helper_text: str,
) -> str:
    guidance_text = render_route_guidance(route)
    example_text = render_route_examples(route)
    return f"""
You are a PostgreSQL analytics SQL generator.
Route: {route}
Use only approved tables from this schema:
{schema_text}

{guidance_text}

{helper_text}

{example_text}

Return strict JSON with keys:
- reasoning
- tables
- sql
- ambiguity

Only generate one read-only PostgreSQL query.
Use psycopg named parameters, including the literal placeholder %(tenant_id)s when tenant filtering is required.
If a referenced table contains tenant_id, the SQL must filter that table by tenant_id.
For joins, include tenant_id filters for each tenant-scoped table alias.
Never use SELECT *.
Prefer explicit aggregate aliases like total_value, warning_count, total_damage_usd, or overlap_count.
For ranking questions, aggregate first, then ORDER BY the aggregate alias DESC, then LIMIT.

Question:
{question}
""".strip()


def build_sql_repair_prompt(
    *,
    question: str,
    schema_text: str,
    route: str,
    helper_text: str,
    bad_sql: str,
    db_error: str,
) -> str:
    guidance_text = render_route_guidance(route)
    example_text = render_route_examples(route)
    return f"""
Repair the PostgreSQL query using the same schema and safety rules.
The repaired SQL must keep or add required tenant filters using %(tenant_id)s.
Route: {route}

Schema:
{schema_text}

{guidance_text}

{helper_text}

{example_text}

Question:
{question}

Failed SQL:
{bad_sql}

Database error:
{db_error}
Return strict JSON with keys:
- reasoning
- tables
- sql
- ambiguity
""".strip()


def build_answer_prompt(
    *,
    question: str,
    sql: str,
    rows: list[dict],
    route: str,
    methodology: str,
) -> str:
    return f"""
Answer the user's question from the SQL results only.
Route: {route}

Return 1-3 sentences of factual natural language only.
Sentence 1 should answer the question directly.
Sentence 2 may mention the next-highest result or the count of matching rows when useful.
Do not mention SQL, prompts, or implementation details.
Do not invent facts beyond the rows.
If no rows are returned, say no matching rows were found for the active tenant.

Question:
{question}

SQL:
{sql}

How It Was Computed:
{methodology}

Rows:
{rows}
""".strip()


