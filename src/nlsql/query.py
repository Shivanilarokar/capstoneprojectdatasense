from __future__ import annotations

from config import AppConfig

from .db import connect_postgres
from .executor import run_validated_sql
from .models import QueryExecutionResult, SqlGenerationResult, ValidationResult
from .openai_client import generate_sql, synthesize_answer
from .prompting import build_answer_prompt, build_sql_generation_prompt, build_sql_repair_prompt
from .schema_introspection import APPROVED_TABLES, format_schema_for_prompt, load_approved_schema
from .validation import validate_generated_sql


def load_schema_context(conn) -> tuple[dict[str, list[dict]], str]:
    schema = load_approved_schema(conn)
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
    schema: dict[str, list[dict]],
    generation: SqlGenerationResult,
    validation: ValidationResult,
    execution: QueryExecutionResult | None,
    params: dict,
    answer: str,
) -> dict:
    return {
        "question": question,
        "schema_tables": list(schema.keys()),
        "generation": _generation_payload(generation),
        "validation": _validation_payload(validation),
        "execution": _execution_payload(execution, params=params) if execution else None,
        "rows": execution.rows if execution else [],
        "answer": answer,
    }


def run_nlsql_query(settings: AppConfig, question: str) -> dict:
    with connect_postgres(settings) as conn:
        schema, schema_text = load_schema_context(conn)
        allowed_tables = set(schema) or set(APPROVED_TABLES)
        tenant_tables = {table for table, columns in schema.items() if any(
            column.get("column_name") == "tenant_id" for column in columns
        )} or set(APPROVED_TABLES)
        params = {"tenant_id": settings.graph_tenant_id}
        repaired = False

        generation = generate_sql(
            settings,
            build_sql_generation_prompt(question=question, schema_text=schema_text),
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
                schema=schema,
                generation=generation,
                validation=validation,
                execution=execution,
                params=params,
                answer=f"NL-SQL execution failed: {execution.error}",
            )

        answer = synthesize_answer(
            settings,
            build_answer_prompt(question=question, sql=execution.sql, rows=execution.rows),
        )
        return {
            "question": question,
            "schema_tables": list(schema.keys()),
            "generation": _generation_payload(generation),
            "validation": _validation_payload(validation),
            "execution": _execution_payload(execution, params=params),
            "rows": execution.rows,
            "answer": answer,
        }
