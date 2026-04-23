from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from config import AppConfig, PROJECT_ROOT
from orchestrator.agent import AgenticOptions, run_agentic_query
from orchestrator.cli import parse_args


class OrchestratorAgentTests(TestCase):
    def _settings(self, *, openai_api_key: str = "") -> AppConfig:
        return AppConfig(
            project_root=PROJECT_ROOT,
            openai_api_key=openai_api_key,
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
            azure_postgres_scope="scope",
        )

    def test_parse_args_accepts_competition_pipelines(self) -> None:
        args = parse_args(["--question", "test", "--force-pipeline", "fullstack"])
        self.assertEqual("fullstack", args.force_pipeline)

    @patch("orchestrator.agent._run_graphrag_route")
    @patch("orchestrator.agent._run_nlsql_route")
    @patch("orchestrator.agent._run_sanctions_route")
    def test_run_agentic_query_fullstack_combines_selected_routes(
        self,
        sanctions_mock,
        nlsql_mock,
        graphrag_mock,
    ) -> None:
        sanctions_mock.return_value = {
            "question": "q",
            "route": "sanctions",
            "answer": "matched",
            "evidence": {"matches": [{"matched_name": "ACME"}]},
            "provenance": {"source_table": "source_ofac_bis_entities"},
            "freshness": {"latest_loaded_at": "2026-04-23T10:00:00Z"},
            "warnings": [],
            "debug": {},
        }
        nlsql_mock.return_value = {
            "question": "q",
            "route": "nlsql",
            "answer": "fda count",
            "evidence": {"rows": [{"company_name": "ACME"}]},
            "provenance": {"sql": "SELECT ..."},
            "freshness": {"note": "sql freshness"},
            "warnings": [],
            "debug": {},
        }
        graphrag_mock.return_value = {
            "question": "q",
            "route": "graphrag",
            "answer": "cascade risk",
            "evidence": {"routes": ["cascade"]},
            "provenance": {"graph_routes": ["cascade"]},
            "freshness": {"note": "graph freshness"},
            "warnings": [],
            "debug": {},
        }

        result = run_agentic_query(
            self._settings(),
            "Is Acme Global sanctioned, which FDA warning letters mention it, and what cascade risk follows?",
            options=AgenticOptions(force_pipeline="fullstack"),
        )

        self.assertEqual("fullstack", result["selected_pipeline"])
        self.assertEqual(["sanctions", "nlsql", "graphrag"], result["routes_executed"])
        self.assertIn("matched", result["answer"])
        self.assertIn("cascade risk", result["answer"])
        self.assertEqual("source_ofac_bis_entities", result["route_results"]["sanctions"]["provenance"]["source_table"])

    @patch("orchestrator.agent._run_nlsql_route")
    def test_run_agentic_query_routes_structured_analytics_to_nlsql(self, nlsql_mock) -> None:
        nlsql_mock.return_value = {
            "question": "q",
            "route": "nlsql",
            "answer": "Illinois had the highest damage.",
            "evidence": {"rows": [{"state": "ILLINOIS", "total_damage_usd": 5877500.0}]},
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

        self.assertEqual("nlsql", result["selected_pipeline"])
        self.assertEqual(["nlsql"], result["routes_executed"])
        self.assertEqual("Illinois had the highest damage.", result["answer"])

    @patch("orchestrator.agent._llm_plan")
    @patch("orchestrator.agent._run_graphrag_route")
    @patch("orchestrator.agent._run_nlsql_route")
    @patch("orchestrator.agent._run_sanctions_route")
    @patch("orchestrator.agent._run_pageindex_route")
    def test_fullstack_route_budget_caps_execution_to_four_unique_routes(
        self,
        pageindex_mock,
        sanctions_mock,
        nlsql_mock,
        graphrag_mock,
        llm_plan_mock,
    ) -> None:
        llm_plan_mock.return_value = {
            "pipeline": "fullstack",
            "routes": ["pageindex", "sanctions", "nlsql", "graphrag", "sanctions"],
            "graph_routes": ["cascade"],
            "confidence": 0.9,
            "reason": "Cross-source question.",
            "planner": "llm",
        }
        pageindex_mock.return_value = {
            "question": "q",
            "route": "pageindex",
            "answer": "sec answer",
            "evidence": {},
            "provenance": {},
            "freshness": {},
            "warnings": [],
            "debug": {},
        }
        sanctions_mock.return_value = {
            "question": "q",
            "route": "sanctions",
            "answer": "sanctions answer",
            "evidence": {},
            "provenance": {},
            "freshness": {},
            "warnings": [],
            "debug": {},
        }
        nlsql_mock.return_value = {
            "question": "q",
            "route": "nlsql",
            "answer": "sql answer",
            "evidence": {},
            "provenance": {},
            "freshness": {},
            "warnings": [],
            "debug": {},
        }
        graphrag_mock.return_value = {
            "question": "q",
            "route": "graphrag",
            "answer": "graph answer",
            "evidence": {},
            "provenance": {},
            "freshness": {},
            "warnings": [],
            "debug": {},
        }

        result = run_agentic_query(
            self._settings(openai_api_key="test-key"),
            "Cross-source risk question",
            options=AgenticOptions(),
        )

        self.assertEqual("fullstack", result["selected_pipeline"])
        self.assertEqual(["pageindex", "sanctions", "nlsql", "graphrag"], result["routes_executed"])
        self.assertTrue(result["route_plan"].get("budget_limited"))
