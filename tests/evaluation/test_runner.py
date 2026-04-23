from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from config import AppConfig, PROJECT_ROOT
from evaluation.runner import run_benchmarks, score_run


class EvaluationRunnerTests(TestCase):
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
            azure_postgres_scope="scope",
        )

    def test_score_run_counts_route_and_provenance_signals(self) -> None:
        benchmark = {"id": "q1", "expected_route": "sanctions", "tags": ["sanctions"]}
        result = {
            "selected_pipeline": "sanctions",
            "provenance": {"source_table": "source_ofac_bis_entities"},
            "freshness": {"status": "ok"},
            "warnings": [],
            "answer": "Matched ACME.",
            "routes_executed": ["sanctions"],
            "route_results": {
                "sanctions": {
                    "evidence": {"matches": [{"matched_name": "ACME"}]},
                    "warnings": [],
                }
            },
        }

        summary = score_run([{"benchmark": benchmark, "result": result}])

        self.assertEqual(1.0, summary["route_accuracy"])
        self.assertEqual(1.0, summary["provenance_coverage"])
        self.assertEqual(1.0, summary["freshness_disclosure_rate"])
        self.assertEqual(1.0, summary["sanctions_decision_explainability"])

    @patch("evaluation.runner.run_agentic_query")
    def test_run_benchmarks_executes_selected_records(self, run_agentic_query_mock) -> None:
        run_agentic_query_mock.side_effect = [
            {
                "selected_pipeline": "nlsql",
                "provenance": {"sql": "SELECT 1"},
                "freshness": {"note": "current"},
                "warnings": [],
                "answer": "Illinois had the highest damage.",
                "routes_executed": ["nlsql"],
                "route_results": {"nlsql": {"evidence": {"rows": [{"state": "ILLINOIS"}]}}},
            },
            {
                "selected_pipeline": "fullstack",
                "provenance": {"sanctions": {}, "nlsql": {}},
                "freshness": {"sanctions": {}, "nlsql": {}},
                "warnings": [],
                "answer": "Acme matched sanctions and appeared in FDA letters.",
                "routes_executed": ["sanctions", "nlsql"],
                "route_results": {
                    "sanctions": {"evidence": {"matches": [{"matched_name": "ACME"}]}},
                    "nlsql": {"evidence": {"rows": [{"company_name": "ACME"}]}},
                },
            },
        ]
        benchmarks = [
            {"id": "q01", "question": "Which states had the highest storm damage?", "expected_route": "nlsql", "tags": ["analytics"]},
            {"id": "q02", "question": "Which sanctioned entities also appear in FDA warning letters?", "expected_route": "fullstack", "tags": ["sanctions", "cross_source"]},
        ]

        report = run_benchmarks(self._settings(), benchmarks=benchmarks)

        self.assertEqual(2, report["benchmark_count"])
        self.assertEqual(2, len(report["records"]))
        self.assertEqual(1.0, report["summary"]["route_accuracy"])
