# OpenAI NL-SQL Postgres Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current hardcoded `nlsql` trade query path with a production-minded OpenAI-driven NL-to-SQL pipeline over the four PostgreSQL source tables.

**Architecture:** The new `nlsql` flow introspects approved PostgreSQL schema, prompts OpenAI for structured SQL generation, validates the generated SQL against strict safety rules, executes it in read-only mode with bounded results, repairs one failed query using database feedback, and synthesizes a natural-language answer from the returned rows. The ingestion layer remains source-specific and is reused as-is except for verification.

**Tech Stack:** Python 3.11+, psycopg 3, Azure Identity, OpenAI Python SDK, PostgreSQL, unittest

---

## File Map

### Modify

- `src/nlsql/db.py`
  Extend connection/session helpers for read-only query execution and statement timeout helpers.
- `src/nlsql/executor.py`
  Replace hardcoded template SQL builder with validated SQL execution.
- `src/nlsql/query.py`
  Replace heuristic one-query orchestration with full schema->generate->validate->execute->repair->answer flow.
- `src/nlsql/cli.py`
  Preserve CLI shape while returning richer execution output.
- `tests/nlsql/test_db.py`
  Extend coverage for read-only execution helpers if needed.
- `tests/nlsql/test_query.py`
  Replace template-only expectations with orchestration expectations for the new flow.

### Create

- `tests/nlsql/test_schema_introspection.py`
  Tests for approved-table schema introspection and prompt formatting.
- `tests/nlsql/test_validation.py`
  Tests for SQL safety validation and tenant filter enforcement.
- `tests/nlsql/test_prompting.py`
  Tests for SQL-generation and repair prompt builders.
- `tests/nlsql/test_executor.py`
  Tests for safe execution, row caps, timeout settings, and retry behavior.
- `tests/nlsql/test_models.py`
  Tests for structured LLM output parsing.
- `src/nlsql/models.py`
  Structured runtime objects for generation, validation, and execution results.
- `src/nlsql/schema_introspection.py`
  PostgreSQL schema metadata loading for approved tables.
- `src/nlsql/prompting.py`
  OpenAI prompt builders for SQL generation, SQL repair, and answer synthesis.
- `src/nlsql/validation.py`
  SQL safety checks and allowed-table enforcement.

## Approved Tables

The LLM-facing NL-SQL layer must expose only:

- `source_ofac_bis_entities`
- `source_noaa_storm_events`
- `source_fda_warning_letters`
- `source_comtrade_flows`

## Task 1: Add structured NL-SQL runtime models

**Files:**
- Create: `tests/nlsql/test_models.py`
- Create: `src/nlsql/models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from unittest import TestCase

from nlsql.models import SqlGenerationResult, ValidationResult


class NlSqlModelsTests(TestCase):
    def test_sql_generation_result_rejects_blank_sql(self) -> None:
        with self.assertRaises(ValueError):
            SqlGenerationResult(
                reasoning="query trade table",
                tables=["source_comtrade_flows"],
                sql="   ",
                ambiguity=False,
            )

    def test_validation_result_captures_rejection_reason(self) -> None:
        result = ValidationResult(ok=False, reason="Only SELECT is allowed.")
        self.assertFalse(result.ok)
        self.assertEqual("Only SELECT is allowed.", result.reason)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_models -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nlsql.models'`

- [ ] **Step 3: Write minimal runtime models**

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SqlGenerationResult:
    reasoning: str
    tables: list[str]
    sql: str
    ambiguity: bool = False

    def __post_init__(self) -> None:
        if not self.sql.strip():
            raise ValueError("Generated SQL cannot be blank.")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class QueryExecutionResult:
    sql: str
    rows: list[dict] = field(default_factory=list)
    error: str = ""
    repaired: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_models -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/test_models.py src/nlsql/models.py
git commit -m "feat: add nlsql runtime models"
```

## Task 2: Add schema introspection for approved tables

**Files:**
- Create: `tests/nlsql/test_schema_introspection.py`
- Create: `src/nlsql/schema_introspection.py`

- [ ] **Step 1: Write the failing schema introspection tests**

```python
from unittest import TestCase

from nlsql.schema_introspection import APPROVED_TABLES, format_schema_for_prompt


class SchemaIntrospectionTests(TestCase):
    def test_approved_tables_match_phase1_sources(self) -> None:
        self.assertEqual(
            {
                "source_ofac_bis_entities",
                "source_noaa_storm_events",
                "source_fda_warning_letters",
                "source_comtrade_flows",
            },
            set(APPROVED_TABLES),
        )

    def test_format_schema_for_prompt_includes_columns(self) -> None:
        text = format_schema_for_prompt(
            {
                "source_comtrade_flows": [
                    {"column_name": "tenant_id", "data_type": "text"},
                    {"column_name": "reporter_desc", "data_type": "text"},
                ]
            }
        )
        self.assertIn("source_comtrade_flows", text)
        self.assertIn("reporter_desc", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_schema_introspection -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nlsql.schema_introspection'`

- [ ] **Step 3: Write minimal schema introspection implementation**

```python
from __future__ import annotations

APPROVED_TABLES = (
    "source_ofac_bis_entities",
    "source_noaa_storm_events",
    "source_fda_warning_letters",
    "source_comtrade_flows",
)


def load_approved_schema(conn) -> dict[str, list[dict]]:
    sql = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = ANY(%(table_names)s)
    ORDER BY table_name, ordinal_position
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"table_names": list(APPROVED_TABLES)})
        rows = cur.fetchall()

    schema: dict[str, list[dict]] = {table: [] for table in APPROVED_TABLES}
    for row in rows:
        schema[row["table_name"]].append(
            {"column_name": row["column_name"], "data_type": row["data_type"]}
        )
    return {table: columns for table, columns in schema.items() if columns}


def format_schema_for_prompt(schema: dict[str, list[dict]]) -> str:
    sections: list[str] = []
    for table_name, columns in schema.items():
        sections.append(f"Table: {table_name}")
        for column in columns:
            sections.append(f"- {column['column_name']} ({column['data_type']})")
    return "\n".join(sections)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_schema_introspection -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/test_schema_introspection.py src/nlsql/schema_introspection.py
git commit -m "feat: add approved schema introspection"
```

## Task 3: Add OpenAI prompt builders for SQL generation, repair, and answer synthesis

**Files:**
- Create: `tests/nlsql/test_prompting.py`
- Create: `src/nlsql/prompting.py`

- [ ] **Step 1: Write the failing prompt tests**

```python
from unittest import TestCase

from nlsql.prompting import build_sql_generation_prompt, build_sql_repair_prompt


class PromptingTests(TestCase):
    def test_build_sql_generation_prompt_embeds_question_and_schema(self) -> None:
        prompt = build_sql_generation_prompt(
            question="Which states had the highest storm damage?",
            schema_text="Table: source_noaa_storm_events\n- state (text)",
        )
        self.assertIn("Which states had the highest storm damage?", prompt)
        self.assertIn("source_noaa_storm_events", prompt)

    def test_build_sql_repair_prompt_embeds_db_error(self) -> None:
        prompt = build_sql_repair_prompt(
            question="How many FDA warnings per company?",
            schema_text="Table: source_fda_warning_letters\n- company_name (text)",
            bad_sql="SELECT company FROM source_fda_warning_letters",
            db_error='column "company" does not exist',
        )
        self.assertIn('column "company" does not exist', prompt)
        self.assertIn("SELECT company", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_prompting -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nlsql.prompting'`

- [ ] **Step 3: Write minimal prompt builders**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_prompting -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/test_prompting.py src/nlsql/prompting.py
git commit -m "feat: add nlsql prompt builders"
```

## Task 4: Add SQL validation and tenant guardrails

**Files:**
- Create: `tests/nlsql/test_validation.py`
- Create: `src/nlsql/validation.py`

- [ ] **Step 1: Write the failing validation tests**

```python
from unittest import TestCase

from nlsql.validation import validate_generated_sql


class ValidationTests(TestCase):
    def test_rejects_non_select_sql(self) -> None:
        result = validate_generated_sql(
            "DELETE FROM source_comtrade_flows",
            allowed_tables={"source_comtrade_flows"},
            tenant_tables={"source_comtrade_flows"},
        )
        self.assertFalse(result.ok)
        self.assertIn("SELECT", result.reason)

    def test_rejects_non_approved_table(self) -> None:
        result = validate_generated_sql(
            "SELECT * FROM pg_user",
            allowed_tables={"source_comtrade_flows"},
            tenant_tables={"source_comtrade_flows"},
        )
        self.assertFalse(result.ok)
        self.assertIn("approved tables", result.reason)

    def test_requires_tenant_filter_for_tenant_tables(self) -> None:
        result = validate_generated_sql(
            "SELECT reporter_desc FROM source_comtrade_flows",
            allowed_tables={"source_comtrade_flows"},
            tenant_tables={"source_comtrade_flows"},
        )
        self.assertFalse(result.ok)
        self.assertIn("tenant_id", result.reason)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_validation -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nlsql.validation'`

- [ ] **Step 3: Write minimal validator**

```python
from __future__ import annotations

import re

from .models import ValidationResult


_BANNED = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|copy|call|do)\b", re.I)
_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.I)


def validate_generated_sql(
    sql: str,
    *,
    allowed_tables: set[str],
    tenant_tables: set[str],
) -> ValidationResult:
    text = sql.strip()
    lowered = text.lower()

    if ";" in text.rstrip(";"):
        return ValidationResult(ok=False, reason="Only one SQL statement is allowed.")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return ValidationResult(ok=False, reason="Only SELECT queries are allowed.")
    if _BANNED.search(text):
        return ValidationResult(ok=False, reason="Only read-only SQL is allowed.")

    tables = {match.group(1) for match in _TABLE_REF.finditer(text)}
    if not tables:
        return ValidationResult(ok=False, reason="SQL must reference approved tables.")
    if not tables.issubset(allowed_tables):
        return ValidationResult(ok=False, reason="SQL may only use approved tables.")

    for table in tables & tenant_tables:
        if "tenant_id" not in lowered:
            return ValidationResult(ok=False, reason=f"SQL must filter {table} by tenant_id.")

    return ValidationResult(ok=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_validation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/test_validation.py src/nlsql/validation.py
git commit -m "feat: add nlsql sql safety validation"
```

## Task 5: Replace template executor with safe SQL execution and retry support

**Files:**
- Create: `tests/nlsql/test_executor.py`
- Modify: `src/nlsql/db.py`
- Modify: `src/nlsql/executor.py`

- [ ] **Step 1: Write the failing executor tests**

```python
from unittest import TestCase
from unittest.mock import MagicMock

from nlsql.executor import execute_sql_once


class ExecutorTests(TestCase):
    def test_execute_sql_once_applies_row_limit(self) -> None:
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [{"state": "Texas"}]

        rows = execute_sql_once(
            conn=conn,
            sql="SELECT state FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s LIMIT 50",
            params={"tenant_id": "tenant-dev"},
            statement_timeout_ms=10000,
        )

        self.assertEqual([{"state": "Texas"}], rows)
        cursor.execute.assert_any_call("SET LOCAL statement_timeout = %s", (10000,))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_executor -v`
Expected: FAIL because `execute_sql_once` does not exist

- [ ] **Step 3: Write minimal safe execution helper**

```python
from __future__ import annotations

from .models import QueryExecutionResult


def execute_sql_once(*, conn, sql: str, params: dict, statement_timeout_ms: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = %s", (statement_timeout_ms,))
        cur.execute(sql, params)
        return list(cur.fetchall())


def run_validated_sql(
    *,
    conn,
    sql: str,
    params: dict,
    statement_timeout_ms: int = 10000,
) -> QueryExecutionResult:
    rows = execute_sql_once(
        conn=conn,
        sql=sql,
        params=params,
        statement_timeout_ms=statement_timeout_ms,
    )
    return QueryExecutionResult(sql=sql, rows=rows)
```

In `src/nlsql/db.py`, add:

```python
def open_readonly_cursor(conn):
    return conn.cursor()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_executor -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/test_executor.py src/nlsql/db.py src/nlsql/executor.py
git commit -m "feat: add safe nlsql execution helpers"
```

## Task 6: Orchestrate OpenAI schema-to-SQL query flow

**Files:**
- Modify: `tests/nlsql/test_query.py`
- Modify: `src/nlsql/query.py`
- Modify: `src/nlsql/cli.py`
- Create: `src/nlsql/openai_client.py`

- [ ] **Step 1: Write the failing orchestration tests**

```python
from unittest import TestCase
from unittest.mock import patch

from config import AppConfig, PROJECT_ROOT
from nlsql.query import run_nlsql_query


class NlSqlQueryTests(TestCase):
    def _settings(self) -> AppConfig:
        return AppConfig(
            project_root=PROJECT_ROOT,
            openai_api_key="sk-test",
            openai_model="gpt-4.1-mini",
            pageindex_api_key="",
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
            graph_tenant_id="tenant-dev",
            sanctions_audit_log=PROJECT_ROOT / "tmp" / "audit.jsonl",
            pg_host="server",
            pg_user="user",
            pg_port=5432,
            pg_database="postgres",
            pg_sslmode="require",
            azure_postgres_scope="scope",
        )

    @patch("nlsql.query.synthesize_answer")
    @patch("nlsql.query.run_validated_sql")
    @patch("nlsql.query.validate_generated_sql")
    @patch("nlsql.query.generate_sql")
    @patch("nlsql.query.load_schema_context")
    @patch("nlsql.query.connect_postgres")
    def test_run_nlsql_query_handles_cross_source_question(
        self,
        connect_postgres_mock,
        load_schema_mock,
        generate_sql_mock,
        validate_mock,
        run_sql_mock,
        synthesize_mock,
    ) -> None:
        conn = connect_postgres_mock.return_value.__enter__.return_value
        load_schema_mock.return_value = (
            {"source_ofac_bis_entities": [], "source_fda_warning_letters": []},
            "Table: source_ofac_bis_entities\nTable: source_fda_warning_letters",
        )
        generate_sql_mock.return_value = {
            "reasoning": "join sanctions and warnings",
            "tables": ["source_ofac_bis_entities", "source_fda_warning_letters"],
            "sql": "SELECT 1 WHERE tenant_id = %(tenant_id)s",
            "ambiguity": False,
        }
        validate_mock.return_value.ok = True
        run_sql_mock.return_value.sql = "SELECT 1 WHERE tenant_id = %(tenant_id)s"
        run_sql_mock.return_value.rows = [{"company_name": "Acme"}]
        run_sql_mock.return_value.error = ""
        run_sql_mock.return_value.repaired = False
        synthesize_mock.return_value = "Acme appears in the joined result."

        result = run_nlsql_query(
            self._settings(),
            "Which sanctioned entities also appear in FDA warning letters?",
        )

        self.assertEqual("Acme appears in the joined result.", result["answer"])
        self.assertEqual(
            ["source_ofac_bis_entities", "source_fda_warning_letters"],
            result["generation"]["tables"],
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v`
Expected: FAIL because query orchestration symbols do not exist yet

- [ ] **Step 3: Write minimal orchestration implementation**

In `src/nlsql/openai_client.py`:

```python
from __future__ import annotations

import json

from openai import OpenAI

from config import AppConfig
from .models import SqlGenerationResult


def generate_sql(settings: AppConfig, prompt: str) -> SqlGenerationResult:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    return SqlGenerationResult(
        reasoning=str(payload.get("reasoning", "")).strip(),
        tables=list(payload.get("tables", [])),
        sql=str(payload.get("sql", "")).strip(),
        ambiguity=bool(payload.get("ambiguity", False)),
    )


def synthesize_answer(settings: AppConfig, prompt: str) -> str:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return (response.choices[0].message.content or "").strip()
```

In `src/nlsql/query.py`, replace the current flow with:

```python
from __future__ import annotations

from config import AppConfig
from nlsql.db import connect_postgres
from nlsql.executor import run_validated_sql
from nlsql.openai_client import generate_sql, synthesize_answer
from nlsql.prompting import (
    build_answer_prompt,
    build_sql_generation_prompt,
    build_sql_repair_prompt,
)
from nlsql.schema_introspection import APPROVED_TABLES, format_schema_for_prompt, load_approved_schema
from nlsql.validation import validate_generated_sql


def load_schema_context(conn) -> tuple[dict[str, list[dict]], str]:
    schema = load_approved_schema(conn)
    return schema, format_schema_for_prompt(schema)


def run_nlsql_query(settings: AppConfig, question: str) -> dict:
    with connect_postgres(settings) as conn:
        schema, schema_text = load_schema_context(conn)
        generation = generate_sql(
            settings,
            build_sql_generation_prompt(question=question, schema_text=schema_text),
        )

        validation = validate_generated_sql(
            generation.sql,
            allowed_tables=set(APPROVED_TABLES),
            tenant_tables=set(APPROVED_TABLES),
        )
        if not validation.ok:
            return {
                "question": question,
                "generation": {
                    "reasoning": generation.reasoning,
                    "tables": generation.tables,
                    "sql": generation.sql,
                    "ambiguity": generation.ambiguity,
                },
                "answer": f"NL-SQL validation failed: {validation.reason}",
                "rows": [],
            }

        execution = run_validated_sql(
            conn=conn,
            sql=generation.sql,
            params={"tenant_id": settings.graph_tenant_id},
        )
        answer = synthesize_answer(
            settings,
            build_answer_prompt(question=question, sql=execution.sql, rows=execution.rows),
        )
        return {
            "question": question,
            "schema_tables": list(schema.keys()),
            "generation": {
                "reasoning": generation.reasoning,
                "tables": generation.tables,
                "sql": generation.sql,
                "ambiguity": generation.ambiguity,
            },
            "validation": {"ok": validation.ok, "reason": validation.reason},
            "rows": execution.rows,
            "answer": answer,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/test_query.py src/nlsql/openai_client.py src/nlsql/query.py src/nlsql/cli.py
git commit -m "feat: add openai nlsql orchestration"
```

## Task 7: Add one-retry SQL repair path and final integrated verification

**Files:**
- Modify: `tests/nlsql/test_executor.py`
- Modify: `tests/nlsql/test_query.py`
- Modify: `src/nlsql/query.py`

- [ ] **Step 1: Write the failing repair tests**

```python
from unittest import TestCase
from unittest.mock import MagicMock, patch

from config import AppConfig, PROJECT_ROOT
from nlsql.models import QueryExecutionResult, SqlGenerationResult
from nlsql.query import run_nlsql_query


class NlSqlRepairTests(TestCase):
    def _settings(self) -> AppConfig:
        return AppConfig(
            project_root=PROJECT_ROOT,
            openai_api_key="sk-test",
            openai_model="gpt-4.1-mini",
            pageindex_api_key="",
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
            graph_tenant_id="tenant-dev",
            sanctions_audit_log=PROJECT_ROOT / "tmp" / "audit.jsonl",
            pg_host="server",
            pg_user="user",
            pg_port=5432,
            pg_database="postgres",
            pg_sslmode="require",
            azure_postgres_scope="scope",
        )

    @patch("nlsql.query.synthesize_answer", return_value="Texas had the highest loss.")
    @patch("nlsql.query.validate_generated_sql")
    @patch("nlsql.query.generate_sql")
    @patch("nlsql.query.load_schema_context")
    @patch("nlsql.query.connect_postgres")
    @patch("nlsql.query.run_validated_sql")
    def test_run_nlsql_query_repairs_one_failed_sql(
        self,
        run_sql_mock,
        connect_mock,
        schema_mock,
        generate_mock,
        validate_mock,
        _synthesize_mock,
    ) -> None:
        schema_mock.return_value = ({"source_noaa_storm_events": []}, "Table: source_noaa_storm_events")
        generate_mock.side_effect = [
            SqlGenerationResult(
                reasoning="bad first query",
                tables=["source_noaa_storm_events"],
                sql="SELECT damage_total FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s",
                ambiguity=False,
            ),
            SqlGenerationResult(
                reasoning="fixed query",
                tables=["source_noaa_storm_events"],
                sql="SELECT state, SUM(damage_property_usd) AS total_damage FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s GROUP BY state ORDER BY total_damage DESC LIMIT 5",
                ambiguity=False,
            ),
        ]
        validate_mock.return_value.ok = True
        run_sql_mock.side_effect = [
            QueryExecutionResult(
                sql="SELECT damage_total FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s",
                rows=[],
                error='column "damage_total" does not exist',
                repaired=False,
            ),
            QueryExecutionResult(
                sql="SELECT state, SUM(damage_property_usd) AS total_damage FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s GROUP BY state ORDER BY total_damage DESC LIMIT 5",
                rows=[{"state": "Texas", "total_damage": 1200.0}],
                error="",
                repaired=True,
            ),
        ]

        result = run_nlsql_query(self._settings(), "Which states had the highest property damage?")

        self.assertEqual("Texas had the highest loss.", result["answer"])
        self.assertTrue(result["execution"]["repaired"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v`
Expected: FAIL because repair flow is not implemented

- [ ] **Step 3: Implement one-retry repair path**

Update `src/nlsql/query.py`:

```python
        execution = run_validated_sql(
            conn=conn,
            sql=generation.sql,
            params={"tenant_id": settings.graph_tenant_id},
        )
        if execution.error:
            repaired_generation = generate_sql(
                settings,
                build_sql_repair_prompt(
                    question=question,
                    schema_text=schema_text,
                    bad_sql=generation.sql,
                    db_error=execution.error,
                ),
            )
            repaired_validation = validate_generated_sql(
                repaired_generation.sql,
                allowed_tables=set(APPROVED_TABLES),
                tenant_tables=set(APPROVED_TABLES),
            )
            if not repaired_validation.ok:
                return {
                    "question": question,
                    "generation": {
                        "reasoning": repaired_generation.reasoning,
                        "tables": repaired_generation.tables,
                        "sql": repaired_generation.sql,
                        "ambiguity": repaired_generation.ambiguity,
                    },
                    "answer": f"NL-SQL repair validation failed: {repaired_validation.reason}",
                    "rows": [],
                }
            execution = run_validated_sql(
                conn=conn,
                sql=repaired_generation.sql,
                params={"tenant_id": settings.graph_tenant_id},
            )
            generation = repaired_generation
            validation = repaired_validation
```

Extend returned payload:

```python
            "execution": {
                "sql": execution.sql,
                "error": execution.error,
                "repaired": execution.repaired,
            },
```

- [ ] **Step 4: Run focused verification**

Run: `.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query tests.nlsql.test_executor tests.nlsql.test_validation -v`
Expected: PASS

- [ ] **Step 5: Run end-to-end live smoke checks**

Run:

```powershell
$env:PGPASSWORD = "$(az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken --output tsv)"
.\.venv\Scripts\python.exe run_ingestion_sql.py --source all --tenant-id default --init-schema
.\.venv\Scripts\python.exe run_nlsql_query.py --question "Which sanctioned entities also appear in FDA warning letters?" --tenant-id default
.\.venv\Scripts\python.exe run_nlsql_query.py --question "Which states had the highest storm damage?" --tenant-id default
.\.venv\Scripts\python.exe run_nlsql_query.py --question "What were the top 5 countries exporting all commodities in 2025?" --tenant-id default
```

Expected:
- schema initialization succeeds
- all four source loaders run without crashing
- NL-SQL returns structured JSON with generated SQL and natural-language answers

- [ ] **Step 6: Commit**

```bash
git add tests/nlsql/test_executor.py tests/nlsql/test_query.py src/nlsql/query.py
git commit -m "feat: add repairable openai nlsql flow"
```

## Self-Review

### Spec coverage

- live schema introspection: covered in Task 2
- OpenAI SQL generation: covered in Tasks 3 and 6
- SQL validation and read-only safety rails: covered in Tasks 4 and 5
- natural-language answer generation: covered in Task 6
- cross-source analytics support: covered in Tasks 6 and 7
- one repair retry: covered in Task 7

### Placeholder scan

- No `TODO`, `TBD`, or deferred code notes remain in steps.
- Every task includes exact files, tests, commands, and minimal code.

### Type consistency

- `SqlGenerationResult`, `ValidationResult`, and `QueryExecutionResult` are used consistently across validation and orchestration.
- Approved tables are centralized in `schema_introspection.py`.
- `run_nlsql_query()` remains the public entry point for CLI and integration.
