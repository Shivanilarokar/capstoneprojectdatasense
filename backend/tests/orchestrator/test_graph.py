from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from backend.config import AppConfig, PROJECT_ROOT
from backend.orchestrator.graph import build_agent_graph, build_agent_mermaid
from backend.orchestrator.router import AgenticOptions, run_agentic_query


class OrchestratorGraphTests(TestCase):
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

    def test_build_agent_graph_returns_compiled_graph(self) -> None:
        graph = build_agent_graph()

        self.assertTrue(hasattr(graph, "invoke"))

    def test_build_agent_mermaid_includes_corrective_nodes(self) -> None:
        mermaid = build_agent_mermaid()

        self.assertIn("grade_route_results", mermaid)
        self.assertIn("rewrite_query", mermaid)
        self.assertIn("increment_retrieval_attempt", mermaid)
        self.assertIn("generate_response", mermaid)
        self.assertIn("grade_hallucination", mermaid)
        self.assertIn("grade_answer_quality", mermaid)
        self.assertIn("increment_iteration", mermaid)

    @patch("backend.orchestrator.router._run_nlsql_route")
    def test_run_agentic_query_exposes_completed_routes_alias(self, nlsql_mock) -> None:
        nlsql_mock.return_value = {
            "status": "ok",
            "question": "q",
            "route": "nlsql",
            "answer": "Illinois had the highest damage.",
            "evidence": {"rows": [{"state": "ILLINOIS"}]},
            "provenance": {"sql": "SELECT ..."},
            "freshness": {"note": "sql freshness"},
            "warnings": [],
            "debug": {},
        }

        result = run_agentic_query(
            self._settings(),
            "Which states had the highest storm damage?",
            options=AgenticOptions(),
        )

        self.assertEqual(["nlsql"], result["completed_routes"])
        self.assertEqual(["nlsql"], result["routes_executed"])
        self.assertTrue(result["correlation_id"])
        self.assertTrue(result["query_id"])
        self.assertIn("checkpoints", result)
        self.assertIn("evidence_sufficiency", result)
        self.assertIn("risk_score", result)
        self.assertIn("risk_score_components", result)
        self.assertIn("compliance", result)

    def test_run_agentic_query_authz_guard_blocks_disallowed_pipeline(self) -> None:
        result = run_agentic_query(
            self._settings(),
            "Is Acme Global sanctioned?",
            options=AgenticOptions(
                force_pipeline="sanctions",
                allowed_pipelines=("nlsql",),
                user_roles=("analyst",),
            ),
        )

        self.assertEqual("denied", result["status"])
        self.assertEqual([], result["routes_executed"])
        self.assertEqual("authz_guard", result["compliance"]["blocked_by"])

    @patch("backend.orchestrator.router._run_sanctions_route")
    @patch("backend.orchestrator.router._run_nlsql_route")
    def test_run_agentic_query_fullstack_adds_risk_and_guard_metadata(
        self,
        nlsql_mock,
        sanctions_mock,
    ) -> None:
        sanctions_mock.return_value = {
            "status": "ok",
            "question": "q",
            "route": "sanctions",
            "answer": "Potential sanctions exposure for ACME.",
            "evidence": {"matches": [{"matched_name": "ACME", "match_type": "primary_exact"}]},
            "provenance": {"source_table": "source_ofac_sdn_entities"},
            "freshness": {"latest_loaded_at": "2026-04-23T10:00:00Z"},
            "warnings": [],
            "debug": {},
        }
        nlsql_mock.return_value = {
            "status": "ok",
            "question": "q",
            "route": "nlsql",
            "answer": "ACME appears in FDA letters.",
            "evidence": {"rows": [{"company_name": "ACME"}]},
            "provenance": {"sql": "SELECT ..."},
            "freshness": {"note": "sql freshness"},
            "warnings": [],
            "debug": {},
        }

        result = run_agentic_query(
            self._settings(),
            "Is Acme Global sanctioned and does it appear in FDA warning letters?",
            options=AgenticOptions(force_pipeline="fullstack"),
        )

        self.assertEqual("ok", result["status"])
        self.assertGreater(result["risk_score"], 0)
        self.assertIn("sanctions", result["risk_score_components"])
        self.assertTrue(result["evidence_sufficiency"]["ok"])
        self.assertTrue(result["compliance"]["checked"])
        self.assertGreaterEqual(len(result["checkpoints"]), 3)
