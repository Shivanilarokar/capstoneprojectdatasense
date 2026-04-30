from __future__ import annotations

import re

from .db import open_readonly_cursor
from .models import QueryExecutionResult

_LITERAL_PERCENT = re.compile(r"%(?!\()")


def _prepare_sql_for_named_params(sql: str) -> str:
    return _LITERAL_PERCENT.sub("%%", sql)


def execute_sql_once(
    *,
    conn,
    sql: str,
    params: dict,
    statement_timeout_ms: int,
    max_rows: int = 200,
) -> list[dict]:
    with open_readonly_cursor(conn) as cur:
        cur.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(statement_timeout_ms),),
        )
        cur.execute(_prepare_sql_for_named_params(sql), params)
        return list(cur.fetchmany(max_rows))


def run_validated_sql(
    *,
    conn,
    sql: str,
    params: dict,
    statement_timeout_ms: int = 10000,
    max_rows: int = 200,
) -> QueryExecutionResult:
    try:
        rows = execute_sql_once(
            conn=conn,
            sql=sql,
            params=params,
            statement_timeout_ms=statement_timeout_ms,
            max_rows=max_rows,
        )
    except Exception as exc:  # noqa: BLE001
        return QueryExecutionResult(sql=sql, rows=[], error=str(exc))
    return QueryExecutionResult(sql=sql, rows=rows)


def build_sql(plan: dict) -> tuple[str, dict]:
    if plan["query_type"] == "trade_top_exporters":
        return (
            """
            SELECT reporter_desc, SUM(primary_value) AS total_value
            FROM source_comtrade_flows
            WHERE tenant_id = %(tenant_id)s
              AND ref_year = %(year)s
              AND flow_code = 'X'
            GROUP BY reporter_desc
            ORDER BY total_value DESC
            LIMIT %(limit)s
            """.strip(),
            {
                "tenant_id": plan["tenant_id"],
                "year": plan["year"],
                "limit": plan["limit"],
            },
        )
    raise ValueError(f"Unsupported query type: {plan['query_type']}")


