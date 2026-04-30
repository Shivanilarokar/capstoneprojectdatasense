from __future__ import annotations

import sys
import types
from unittest import TestCase
from unittest.mock import patch

from backend.config import AppConfig, PROJECT_ROOT
from backend.orchestrator.router import AgenticOptions
from backend.orchestrator.tools import build_route_tools, build_router_model


class _FakeChatOpenAI:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class OrchestratorToolTests(TestCase):
    def _settings(self) -> AppConfig:
        return AppConfig(
            project_root=PROJECT_ROOT,
            openai_api_key="test-key",
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

    def test_build_router_model_uses_langchain_openai_when_available(self) -> None:
        fake_module = types.ModuleType("langchain_openai")
        fake_module.ChatOpenAI = _FakeChatOpenAI

        with patch.dict(sys.modules, {"langchain_openai": fake_module}):
            model = build_router_model("gpt-4.1-mini", api_key="test-key")

        self.assertIsInstance(model, _FakeChatOpenAI)
        self.assertEqual("gpt-4.1-mini", model.kwargs["model"])
        self.assertEqual("test-key", model.kwargs["api_key"])
        self.assertEqual(0, model.kwargs["temperature"])

    @patch("backend.nlsql.query.run_nlsql_query")
    def test_nlsql_tool_returns_normalized_route_envelope(self, run_nlsql_query_mock) -> None:
        run_nlsql_query_mock.return_value = {
            "question": "Which states had the highest storm damage?",
            "schema_tables": ["source_noaa_storm_events"],
            "generation": {"sql": "SELECT state FROM source_noaa_storm_events"},
            "validation": {"ok": True, "reason": ""},
            "execution": {
                "sql": "SELECT state FROM source_noaa_storm_events",
                "params": {"tenant_id": "tenant-dev"},
                "row_count": 1,
                "error": None,
                "repaired": False,
            },
            "rows": [{"state": "ILLINOIS"}],
            "answer": "Illinois had the highest damage.",
        }

        tools = build_route_tools(
            self._settings(),
            user_id="system",
            options=AgenticOptions(),
        )
        self.assertIn("fullstack", tools)
        result = tools["nlsql"].invoke({"question": "Which states had the highest storm damage?"})

        self.assertEqual("ok", result["status"])
        self.assertEqual("nlsql", result["route"])
        self.assertEqual("Illinois had the highest damage.", result["answer"])
        self.assertIn("provenance", result)
        self.assertIn("freshness", result)



