from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from backend.app.services.orchestrator_service import ask_supplychainnexus
from backend.config import AppConfig, PROJECT_ROOT


class OrchestratorServiceTests(TestCase):
    @patch("backend.app.services.orchestrator_service.run_agentic_query")
    def test_ask_supplychainnexus_attaches_answer_graph(self, run_agentic_query_mock) -> None:
        run_agentic_query_mock.return_value = {
            "status": "ok",
            "question": "Show cascade exposure for ACME",
            "answer": "Cascade exposure found.",
            "selected_pipeline": "graphrag",
            "route_plan": {"pipeline": "graphrag", "routes": ["graphrag"]},
            "warnings": [],
            "query_id": "query-789",
            "routes_executed": ["graphrag"],
            "route_results": {
                "graphrag": {
                    "evidence": {
                        "results": [
                            {
                                "route": "cascade",
                                "multi_tier_paths": [
                                    {"company": "ACME", "tier1_supplier": "Tier1 Metals"}
                                ],
                            }
                        ]
                    }
                }
            },
        }

        result = ask_supplychainnexus(
            settings=AppConfig(
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
            ),
            question="Show cascade exposure for ACME",
            user_id="user-1",
            roles=("analyst",),
        )

        self.assertIn("answer_graph", result)
        self.assertEqual("query-789", result["answer_graph"]["query_id"])
        self.assertGreaterEqual(result["answer_graph"]["stats"]["node_count"], 2)
