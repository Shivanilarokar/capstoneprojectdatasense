from __future__ import annotations

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
