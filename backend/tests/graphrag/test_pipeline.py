from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from backend.config import load_app_config
from backend.graphrag.pipeline import build_graph_sync_batches, sync_graph_state


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

    def test_sync_graph_state_uses_local_sources(self) -> None:
        settings = load_app_config(tenant_id_override="tenant-dev")

        class FakeStore:
            instances = []

            def __init__(self, _settings):
                self.write_calls = []
                type(self).instances.append(self)

            def write_rows(self, cypher, rows, tenant_id, batch_size=500):
                self.write_calls.append((cypher, list(rows), tenant_id, batch_size))

            def close(self):
                return None

        sections_path = settings.project_root / "backend" / "tests" / "graphrag" / "_tmp_sections.json"
        try:
            sections_path.write_text(
                json.dumps(
                    [
                        {
                            "ticker": "AAPL",
                            "company_name": "Apple Inc.",
                            "cik": "0000320193",
                            "filing_date": "2025-10-31",
                            "filing_document_url": "https://example.com/aapl",
                            "sections": {"item1a": "Apple relies on TSMC for manufacturing."},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with (
                patch(
                    "backend.graphrag.pipeline._load_local_graph_rows",
                    return_value=(
                        {
                            "ofac_sdn": [
                                {
                                    "source_entity_id": "s1",
                                    "primary_name": "ACME GLOBAL LTD",
                                    "aliases": "Acme Global",
                                    "sanctions_type": "Entity",
                                    "sanctions_programs": "SDN",
                                    "date_published": "2026-04-20",
                                    "address_text": "Dubai",
                                    "source_file_name": "sdn.xlsx",
                                }
                            ],
                            "comtrade": [
                                {
                                    "ref_year": 2025,
                                    "reporter_desc": "United States",
                                    "partner_desc": "Taiwan",
                                    "cmd_code": "8542",
                                    "cmd_desc": "Electronic integrated circuits",
                                    "flow_desc": "Export",
                                    "primary_value": 1000.0,
                                    "qty": 5.0,
                                    "net_wgt": 10.0,
                                }
                            ],
                            "noaa": [
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
                                    "end_lat": None,
                                    "end_lon": None,
                                }
                            ],
                            "fda": [
                                {
                                    "source_record_hash": "r1",
                                    "company_name": "Acme Global Ltd",
                                    "letter_issue_date": "2026-04-01",
                                    "subject": "Sterility failures",
                                    "issuing_office": "CDER",
                                }
                            ],
                        },
                        {
                            "ofac_sdn": "data/ingestion/ofac_sdn/sdn_data.xlsx",
                            "comtrade": "data/ingestion/comtrade/TradeData.xlsx",
                            "noaa": "data/ingestion/noaa/storm.csv",
                            "fda": "data/ingestion/fda/warning-letters.xlsx",
                        },
                    ),
                ),
                patch("backend.graphrag.pipeline.Neo4jStore", FakeStore),
                patch("backend.graphrag.pipeline.build_multi_tier_topology", return_value={"status": "ok"}),
            ):
                summary = sync_graph_state(settings, sections_json_path=sections_path)
        finally:
            sections_path.unlink(missing_ok=True)

        self.assertEqual(summary["source_mode"], "local_files")
        self.assertEqual(summary["topology"], {"status": "ok"})
        self.assertEqual(summary["batches"]["sanctions"]["entities"], 1)
        self.assertEqual(summary["batches"]["trade"]["flows"], 1)
        self.assertTrue(FakeStore.instances)
        self.assertGreater(len(FakeStore.instances[0].write_calls), 0)




