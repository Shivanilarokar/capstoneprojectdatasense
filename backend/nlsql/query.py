from __future__ import annotations

from backend.config import AppConfig

from .classifier import classify_question
from .db import connect_postgres
from .executor import run_validated_sql
from .joins import helper_text_for_route
from .models import QueryExecutionResult, SqlGenerationResult, ValidationResult
from .openai_client import generate_sql, synthesize_answer
from .presentation import build_evidence_lines, format_rows_for_display, render_answer_first, summarize_methodology
from .prompting import build_answer_prompt, build_sql_generation_prompt, build_sql_repair_prompt
from .schema_introspection import APPROVED_TABLES, format_schema_for_prompt, load_approved_schema
from .validation import validate_generated_sql


def _order_schema(
    schema: dict[str, list[dict]],
    preferred_tables: list[str],
) -> dict[str, list[dict]]:
    ordered: dict[str, list[dict]] = {}
    for table in preferred_tables:
        if table in schema:
            ordered[table] = schema[table]
    for table, columns in schema.items():
        if table not in ordered:
            ordered[table] = columns
    return ordered


def load_schema_context(conn, preferred_tables: list[str] | None = None) -> tuple[dict[str, list[dict]], str]:
    schema = load_approved_schema(conn)
    if preferred_tables:
        schema = _order_schema(schema, preferred_tables)
    return schema, format_schema_for_prompt(schema)


def _generation_payload(generation: SqlGenerationResult) -> dict:
    return {
        "reasoning": generation.reasoning,
        "tables": generation.tables,
        "sql": generation.sql,
        "ambiguity": generation.ambiguity,
    }


def _validation_payload(validation: ValidationResult) -> dict:
    return {"ok": validation.ok, "reason": validation.reason}


def _execution_payload(execution: QueryExecutionResult, *, params: dict) -> dict:
    return {
        "sql": execution.sql,
        "params": params,
        "row_count": len(execution.rows),
        "error": execution.error,
        "repaired": execution.repaired,
    }


def _failure_response(
    *,
    question: str,
    classification: dict,
    schema: dict[str, list[dict]],
    generation: SqlGenerationResult,
    validation: ValidationResult,
    execution: QueryExecutionResult | None,
    params: dict,
    answer: str,
) -> dict:
    rows = execution.rows if execution else []
    formatted_rows = format_rows_for_display(rows)
    methodology = summarize_methodology(
        route=classification.get("route", "unsupported"),
        sql=execution.sql if execution else generation.sql,
        row_count=len(rows),
    )
    rendered_output = render_answer_first(
        question=question,
        answer=answer,
        methodology=methodology,
        evidence_lines=build_evidence_lines(formatted_rows),
    )
    return {
        "question": question,
        "classification": classification,
        "schema_tables": list(schema.keys()),
        "generation": _generation_payload(generation),
        "validation": _validation_payload(validation),
        "execution": _execution_payload(execution, params=params) if execution else None,
        "rows": rows,
        "formatted_rows": formatted_rows,
        "methodology": methodology,
        "rendered_output": rendered_output,
        "answer": answer,
        "debug_payload": {
            "question": question,
            "classification": classification,
            "schema_tables": list(schema.keys()),
            "generation": _generation_payload(generation),
            "validation": _validation_payload(validation),
            "execution": _execution_payload(execution, params=params) if execution else None,
            "rows": rows,
            "answer": answer,
        },
    }


def run_nlsql_query(settings: AppConfig, question: str) -> dict:
    with connect_postgres(settings) as conn:
        classification = classify_question(question)
        schema, schema_text = load_schema_context(conn, preferred_tables=classification.preferred_tables)
        allowed_tables = set(schema) or set(APPROVED_TABLES)
        tenant_tables = {table for table, columns in schema.items() if any(
            column.get("column_name") == "tenant_id" for column in columns
        )} or set(APPROVED_TABLES)
        params = {"tenant_id": settings.graph_tenant_id}
        repaired = False
        helper_text = helper_text_for_route(classification.route)

        if classification.route == "unsupported":
            answer = (
                "This NL-SQL route could not confidently map the question to the current NOAA, Comtrade, "
                "FDA, or OFAC source tables."
            )
            methodology = "No SQL was generated because the deterministic classifier marked the question as unsupported."
            rendered_output = render_answer_first(
                question=question,
                answer=answer,
                methodology=methodology,
                evidence_lines=["No SQL executed."],
            )
            debug_payload = {
                "question": question,
                "classification": {
                    "route": classification.route,
                    "reason": classification.reason,
                    "preferred_tables": classification.preferred_tables,
                },
                "schema_tables": list(schema.keys()),
                "generation": None,
                "validation": None,
                "execution": None,
                "rows": [],
                "answer": answer,
            }
            return {
                "question": question,
                "classification": debug_payload["classification"],
                "schema_tables": list(schema.keys()),
                "generation": None,
                "validation": None,
                "execution": None,
                "rows": [],
                "formatted_rows": [],
                "methodology": methodology,
                "rendered_output": rendered_output,
                "answer": answer,
                "debug_payload": debug_payload,
            }

        generation = generate_sql(
            settings,
            build_sql_generation_prompt(
                question=question,
                schema_text=schema_text,
                route=classification.route,
                helper_text=helper_text,
            ),
        )
        validation = validate_generated_sql(
            generation.sql,
            allowed_tables=allowed_tables,
            tenant_tables=tenant_tables,
        )
        if not validation.ok:
            generation = generate_sql(
                settings,
                build_sql_repair_prompt(
                    question=question,
                    schema_text=schema_text,
                    route=classification.route,
                    helper_text=helper_text,
                    bad_sql=generation.sql,
                    db_error=validation.reason,
                ),
            )
            validation = validate_generated_sql(
                generation.sql,
                allowed_tables=allowed_tables,
                tenant_tables=tenant_tables,
            )
            repaired = True
            if not validation.ok:
                return _failure_response(
                    question=question,
                    classification={
                        "route": classification.route,
                        "reason": classification.reason,
                        "preferred_tables": classification.preferred_tables,
                    },
                    schema=schema,
                    generation=generation,
                    validation=validation,
                    execution=None,
                    params=params,
                    answer=f"NL-SQL validation failed: {validation.reason}",
                )

        execution = run_validated_sql(
            conn=conn,
            sql=generation.sql,
            params=params,
        )
        if repaired and not execution.error:
            execution = QueryExecutionResult(
                sql=execution.sql,
                rows=execution.rows,
                error=execution.error,
                repaired=True,
            )

        if execution.error and not repaired:
            repaired_generation = generate_sql(
                settings,
                build_sql_repair_prompt(
                    question=question,
                    schema_text=schema_text,
                    route=classification.route,
                    helper_text=helper_text,
                    bad_sql=generation.sql,
                    db_error=execution.error,
                ),
            )
            repaired_validation = validate_generated_sql(
                repaired_generation.sql,
                allowed_tables=allowed_tables,
                tenant_tables=tenant_tables,
            )
            if not repaired_validation.ok:
                return _failure_response(
                    question=question,
                    classification={
                        "route": classification.route,
                        "reason": classification.reason,
                        "preferred_tables": classification.preferred_tables,
                    },
                    schema=schema,
                    generation=repaired_generation,
                    validation=repaired_validation,
                    execution=execution,
                    params=params,
                    answer=f"NL-SQL repair validation failed: {repaired_validation.reason}",
                )

            repaired_execution = run_validated_sql(
                conn=conn,
                sql=repaired_generation.sql,
                params=params,
            )
            execution = QueryExecutionResult(
                sql=repaired_execution.sql,
                rows=repaired_execution.rows,
                error=repaired_execution.error,
                repaired=True,
            )
            generation = repaired_generation
            validation = repaired_validation
            repaired = True

        if execution.error:
            return _failure_response(
                question=question,
                classification={
                    "route": classification.route,
                    "reason": classification.reason,
                    "preferred_tables": classification.preferred_tables,
                },
                schema=schema,
                generation=generation,
                validation=validation,
                execution=execution,
                params=params,
                answer=f"NL-SQL execution failed: {execution.error}",
            )

        formatted_rows = format_rows_for_display(execution.rows)
        methodology = summarize_methodology(
            route=classification.route,
            sql=execution.sql,
            row_count=len(execution.rows),
        )
        answer = synthesize_answer(
            settings,
            build_answer_prompt(
                question=question,
                sql=execution.sql,
                rows=formatted_rows,
                route=classification.route,
                methodology=methodology,
            ),
        )
        classification_payload = {
            "route": classification.route,
            "reason": classification.reason,
            "preferred_tables": classification.preferred_tables,
        }
        debug_payload = {
            "question": question,
            "classification": classification_payload,
            "schema_tables": list(schema.keys()),
            "generation": _generation_payload(generation),
            "validation": _validation_payload(validation),
            "execution": _execution_payload(execution, params=params),
            "rows": execution.rows,
            "answer": answer,
        }
        rendered_output = render_answer_first(
            question=question,
            answer=answer,
            methodology=methodology,
            evidence_lines=build_evidence_lines(formatted_rows),
        )
        return {
            "question": question,
            "classification": classification_payload,
            "schema_tables": list(schema.keys()),
            "generation": _generation_payload(generation),
            "validation": _validation_payload(validation),
            "execution": _execution_payload(execution, params=params),
            "rows": execution.rows,
            "formatted_rows": formatted_rows,
            "methodology": methodology,
            "rendered_output": rendered_output,
            "answer": answer,
            "debug_payload": debug_payload,
        }


