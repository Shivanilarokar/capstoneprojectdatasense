from __future__ import annotations

from unittest import TestCase


class DomainImportTests(TestCase):
    def test_domain_packages_import(self) -> None:
        from backend.graphrag.query import run_graph_query
        from backend.ingestion.ingestion_cli import run_ingestion
        from backend.nlsql.query import run_nlsql_query
        from backend.orchestrator.router import AgenticOptions
        from backend.pageindex.pipeline import run_pipeline
        from backend.sanctions.query import run_sanctions_query

        self.assertEqual("AgenticOptions", AgenticOptions.__name__)
        self.assertTrue(callable(run_graph_query))
        self.assertTrue(callable(run_ingestion))
        self.assertTrue(callable(run_nlsql_query))
        self.assertTrue(callable(run_pipeline))
        self.assertTrue(callable(run_sanctions_query))


