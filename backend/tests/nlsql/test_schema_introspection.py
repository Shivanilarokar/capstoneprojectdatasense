from __future__ import annotations

from unittest import TestCase

from backend.nlsql.schema_introspection import APPROVED_TABLES, format_schema_for_prompt


class SchemaIntrospectionTests(TestCase):
    def test_approved_tables_match_phase1_sources(self) -> None:
        self.assertEqual(
            {
                "source_ofac_sdn_entities",
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



