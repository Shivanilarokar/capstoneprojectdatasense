from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock

from backend.nlsql.executor import execute_sql_once, run_validated_sql


class ExecutorTests(TestCase):
    def test_execute_sql_once_applies_readonly_and_timeout(self) -> None:
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchmany.return_value = [{"state": "Texas"}]

        rows = execute_sql_once(
            conn=conn,
            sql="SELECT state FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s LIMIT 50",
            params={"tenant_id": "tenant-dev"},
            statement_timeout_ms=10000,
            max_rows=1,
        )

        self.assertEqual([{"state": "Texas"}], rows)
        cursor.execute.assert_any_call("SET default_transaction_read_only = on")
        cursor.execute.assert_any_call(
            "SELECT set_config('statement_timeout', %s, false)",
            ("10000",),
        )
        cursor.fetchmany.assert_called_once_with(1)

    def test_run_validated_sql_captures_execution_error(self) -> None:
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = [
            None,
            None,
            RuntimeError('column "damage_total" does not exist'),
        ]

        result = run_validated_sql(
            conn=conn,
            sql="SELECT damage_total FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s",
            params={"tenant_id": "tenant-dev"},
            statement_timeout_ms=10000,
        )

        self.assertEqual([], result.rows)
        self.assertIn('column "damage_total" does not exist', result.error)

    def test_execute_sql_once_escapes_literal_percent_for_named_parameters(self) -> None:
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchmany.return_value = []

        execute_sql_once(
            conn=conn,
            sql=(
                "SELECT primary_name FROM source_ofac_sdn_entities "
                "WHERE tenant_id = %(tenant_id)s "
                "AND aliases ILIKE '%' || primary_name || '%'"
            ),
            params={"tenant_id": "default"},
            statement_timeout_ms=10000,
        )

        cursor.execute.assert_any_call(
            "SELECT primary_name FROM source_ofac_sdn_entities "
            "WHERE tenant_id = %(tenant_id)s "
            "AND aliases ILIKE '%%' || primary_name || '%%'",
            {"tenant_id": "default"},
        )



