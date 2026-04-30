from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from backend.config import AppConfig, PROJECT_ROOT
from backend.orchestrator.router import AgenticOptions, run_agentic_query


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
            pg_connect_timeout=15,
            azure_postgres_scope="scope",
        )

    @patch("backend.orchestrator.router._run_graphrag_route")
    @patch("backend.orchestrator.router._run_nlsql_route")
    @patch("backend.orchestrator.router._run_sanctions_route")
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
            "provenance": {"source_table": "source_ofac_sdn_entities"},
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
        self.assertEqual("source_ofac_sdn_entities", result["route_results"]["sanctions"]["provenance"]["source_table"])

    @patch("backend.orchestrator.router._run_nlsql_route")
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

    @patch("backend.orchestrator.router._run_graphrag_route")
    @patch("backend.orchestrator.router._run_nlsql_route")
    @patch("backend.orchestrator.router._run_sanctions_route")
    @patch("backend.orchestrator.router._run_pageindex_route")
    @patch("backend.orchestrator.planner.plan_query")
    def test_fullstack_route_budget_caps_execution_to_four_unique_routes(
        self,
        plan_query_mock,
        pageindex_mock,
        sanctions_mock,
        nlsql_mock,
        graphrag_mock,
    ) -> None:
        plan_query_mock.return_value = {
            "plan_type": "multi",
            "pipeline": "fullstack",
            "routes": ["pageindex", "sanctions", "nlsql", "graphrag", "sanctions"],
            "graph_routes": ["cascade"],
            "confidence": 0.9,
            "reason": "Cross-source question.",
            "planner": "heuristic",
            "tier_hint": "tier_2",
            "subquestions": [
                {"question": "filings", "route_hint": "pageindex"},
                {"question": "sanctions", "route_hint": "sanctions"},
                {"question": "sql", "route_hint": "nlsql"},
                {"question": "graph", "route_hint": "graphrag"},
            ],
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
            self._settings(),
            "Review the latest 10-K disclosure, sanctions risk, FDA letters, and downstream cascade exposure for Acme.",
            options=AgenticOptions(),
        )

        self.assertEqual("fullstack", result["selected_pipeline"])
        self.assertEqual(["pageindex", "sanctions", "nlsql", "graphrag"], result["routes_executed"])
        self.assertTrue(result["route_plan"].get("budget_limited"))

    @patch("backend.orchestrator.grader.grade_answer_quality")
    @patch("backend.orchestrator.grader.grade_hallucination")
    @patch("backend.orchestrator.query_rewriter.rewrite_query")
    @patch("backend.orchestrator.grader.grade_route_results")
    @patch("backend.orchestrator.router._run_tool_for_route")
    def test_run_agentic_query_rewrites_once_when_grading_is_weak(
        self,
        run_tool_for_route_mock,
        grade_route_results_mock,
        rewrite_query_mock,
        grade_hallucination_mock,
        grade_answer_quality_mock,
    ) -> None:
        seen_questions: list[str] = []

        def run_tool(*, route: str, question: str, state):
            seen_questions.append(question)
            return {
                "status": "ok",
                "question": question,
                "route": route,
                "answer": f"Answer for {question}",
                "evidence": {"rows": [{"question": question}]},
                "provenance": {"sql": "SELECT ..."},
                "freshness": {"note": "sql freshness"},
                "warnings": [],
                "debug": {},
            }

        run_tool_for_route_mock.side_effect = run_tool
        grade_route_results_mock.side_effect = [
            {
                "filtered_route_results": {},
                "route_relevance": ["no"],
                "relevant_route_count": 0,
                "rewrite_recommended": True,
                "rewrite_reason": "The first pass was too generic.",
            },
            {
                "filtered_route_results": {
                    "nlsql": {
                        "status": "ok",
                        "question": "storm damage by state from NOAA storm events",
                        "route": "nlsql",
                        "answer": "Illinois had the highest damage.",
                        "evidence": {"rows": [{"state": "ILLINOIS"}]},
                        "provenance": {"sql": "SELECT ..."},
                        "freshness": {"note": "sql freshness"},
                        "warnings": [],
                        "debug": {},
                    }
                },
                "route_relevance": ["yes"],
                "relevant_route_count": 1,
                "rewrite_recommended": False,
                "rewrite_reason": "",
            },
        ]
        rewrite_query_mock.return_value = {
            "rewritten_question": "storm damage by state from NOAA storm events",
            "effective_question": "storm damage by state from NOAA storm events",
        }
        grade_hallucination_mock.return_value = {"hallucination_grade": "yes"}
        grade_answer_quality_mock.return_value = {"answer_quality_grade": "yes"}

        result = run_agentic_query(
            self._settings(),
            "Which states had the highest storm damage?",
            options=AgenticOptions(enable_query_rewrite=True, enable_grading=True, max_rewrite_attempts=1),
        )

        self.assertEqual(
            [
                "Which states had the highest storm damage?",
                "storm damage by state from NOAA storm events",
            ],
            seen_questions,
        )
        self.assertEqual("storm damage by state from NOAA storm events", result["rewritten_question"])
        self.assertEqual("yes", result["hallucination_grade"])
        self.assertEqual("yes", result["answer_quality_grade"])


