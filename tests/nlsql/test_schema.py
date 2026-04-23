from __future__ import annotations

from unittest import TestCase

from ingestion.base import build_upsert_statement, stable_record_hash
from nlsql.schema import SOURCE_TABLE_DDLS


class SchemaTests(TestCase):
    def test_source_table_ddls_cover_all_phase1_sources(self) -> None:
        self.assertEqual(
            {
                "source_ofac_bis_entities",
                "source_comtrade_flows",
                "source_noaa_storm_events",
                "source_fda_warning_letters",
            },
            set(SOURCE_TABLE_DDLS.keys()),
        )

    def test_stable_record_hash_is_deterministic(self) -> None:
        self.assertEqual(
            stable_record_hash("tenant-dev", "acme", "2025-01-01"),
            stable_record_hash("tenant-dev", "acme", "2025-01-01"),
        )

    def test_build_upsert_statement_uses_conflict_keys(self) -> None:
        sql = build_upsert_statement(
            "source_fda_warning_letters",
            ["tenant_id", "source_record_hash", "company_name"],
            ["tenant_id", "source_record_hash"],
        )
        self.assertIn("INSERT INTO source_fda_warning_letters", sql)
        self.assertIn("ON CONFLICT (tenant_id, source_record_hash)", sql)
        self.assertIn("company_name = EXCLUDED.company_name", sql)
