from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from backend.config import AppConfig, PROJECT_ROOT
from backend.sanctions.query import run_sanctions_query


class SanctionsQueryTests(TestCase):
    def _settings(self) -> AppConfig:
        return AppConfig(
            project_root=PROJECT_ROOT,
            openai_api_key="",
            openai_model="gpt-4.1-mini",
            pageindex_api_key="",
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
            graph_tenant_id="tenant-dev",
            sanctions_audit_log=PROJECT_ROOT / "tmp" / "audit.jsonl",
            pg_host="server",
            pg_user="user",
            pg_port=5432,
            pg_database="postgres",
            pg_sslmode="require",
            pg_connect_timeout=15,
            azure_postgres_scope="scope",
        )

    @patch("backend.sanctions.query._append_jsonl")
    @patch("backend.sanctions.query.connect_postgres")
    def test_run_sanctions_query_returns_match_envelope(self, connect_mock, append_mock) -> None:
        conn = connect_mock.return_value.__enter__.return_value
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            {
                "source_entity_id": "100",
                "primary_name": "ACME TRADING LLC",
                "aliases": "Acme Trading; Acme Global",
                "sanctions_programs": "SDN",
                "sanctions_type": "Entity",
                "source_file_name": "sdn_data.xlsx",
                "source_loaded_at": "2026-04-23T10:00:00Z",
            }
        ]

        result = run_sanctions_query(
            self._settings(),
            "Is Acme Global sanctioned?",
            entity_names=["Acme Global"],
        )

        self.assertEqual("sanctions", result["route"])
        self.assertEqual("tenant-dev", result["tenant_id"])
        self.assertEqual(["Acme Global"], result["evidence"]["entities"])
        self.assertEqual(1, len(result["evidence"]["matches"]))
        self.assertEqual("source_ofac_sdn_entities", result["provenance"]["source_table"])
        self.assertEqual("2026-04-23T10:00:00Z", result["freshness"]["latest_loaded_at"])
        self.assertEqual([], result["warnings"])
        append_mock.assert_called_once()

    @patch("backend.sanctions.query._append_jsonl")
    @patch("backend.sanctions.query.connect_postgres")
    def test_run_sanctions_query_warns_when_no_entities_can_be_extracted(
        self,
        connect_mock,
        append_mock,
    ) -> None:
        conn = connect_mock.return_value.__enter__.return_value
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        result = run_sanctions_query(self._settings(), "What sanctions issues exist?")

        self.assertEqual("sanctions", result["route"])
        self.assertIn("No entity names were extracted", result["warnings"][0])
        self.assertEqual([], result["evidence"]["matches"])
        append_mock.assert_called_once()




