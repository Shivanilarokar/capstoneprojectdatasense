from __future__ import annotations

from unittest import TestCase

from graphrag.pipeline import build_graph_sync_batches


class GraphPipelineTests(TestCase):
    def test_build_graph_sync_batches_emits_all_core_domains(self) -> None:
        sections = [
            {
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "cik": "0000320193",
                "filing_date": "2025-10-31",
                "filing_document_url": "https://example.com/aapl",
                "sections": {
                    "item1a": "Apple relies on Hon Hai Precision Industry and TSMC for manufacturing capacity.",
                    "item7": "Supply chain concentration remains a risk.",
                },
            }
        ]
        sanctions_rows = [
            {
                "source_entity_id": "s1",
                "primary_name": "ACME GLOBAL LTD",
                "aliases": "Acme Global",
                "sanctions_type": "Entity",
                "date_published": "2026-04-20",
                "source_file_name": "sdn.xlsx",
            }
        ]
        trade_rows = [
            {
                "ref_year": 2025,
                "reporter_desc": "United States",
                "partner_desc": "Taiwan",
                "cmd_code": "8542",
                "cmd_desc": "Electronic integrated circuits",
                "flow_desc": "Export",
                "primary_value": 1000.0,
            }
        ]
        hazard_rows = [
            {
                "event_id": 1,
                "state": "TEXAS",
                "cz_name": "HARRIS",
                "year": 2025,
                "event_type": "Hurricane",
                "damage_property_usd": 500.0,
                "damage_crops_usd": 0.0,
                "begin_lat": 29.76,
                "begin_lon": -95.36,
            }
        ]
        regulatory_rows = [
            {
                "source_record_hash": "r1",
                "company_name": "Acme Global Ltd",
                "letter_issue_date": "2026-04-01",
                "subject": "Sterility failures",
                "issuing_office": "CDER",
            }
        ]

        batches = build_graph_sync_batches(
            tenant_id="tenant-dev",
            sections=sections,
            sanctions_rows=sanctions_rows,
            trade_rows=trade_rows,
            hazard_rows=hazard_rows,
            regulatory_rows=regulatory_rows,
        )

        self.assertIn("sec_filings", batches)
        self.assertIn("sanctions", batches)
        self.assertIn("trade", batches)
        self.assertIn("hazards", batches)
        self.assertIn("regulatory", batches)
        self.assertTrue(batches["sec_filings"])
