from __future__ import annotations

from unittest import TestCase

from backend.nlsql.models import SqlGenerationResult, ValidationResult


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



