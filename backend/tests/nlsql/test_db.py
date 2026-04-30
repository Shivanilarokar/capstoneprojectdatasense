from __future__ import annotations

import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from backend.config import AppConfig, PROJECT_ROOT
from backend.nlsql.db import connect_postgres


class PostgresConnectionTests(TestCase):
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
            pg_host="postgescapstoneproject.postgres.database.azure.com",
            pg_user="sweetyshivzz454@gmail.com",
            pg_port=5432,
            pg_database="postgres",
            pg_sslmode="require",
            pg_connect_timeout=15,
            azure_postgres_scope="https://ossrdbms-aad.database.windows.net/.default",
        )

    @patch("backend.nlsql.db.socket.create_connection")
    @patch("backend.nlsql.db.psycopg.connect")
    @patch("backend.nlsql.db.DefaultAzureCredential")
    def test_connect_postgres_uses_defaultazurecredential_token(
        self,
        credential_cls,
        connect_mock,
        socket_connect_mock,
    ) -> None:
        socket_connect_mock.return_value = MagicMock()
        credential = credential_cls.return_value
        credential.get_token.return_value = SimpleNamespace(token="aad-token")

        connect_postgres(self._settings())

        credential.get_token.assert_called_once_with(
            "https://ossrdbms-aad.database.windows.net/.default"
        )
        kwargs = connect_mock.call_args.kwargs
        self.assertEqual("aad-token", kwargs["password"])
        self.assertEqual("postgescapstoneproject.postgres.database.azure.com", kwargs["host"])
        self.assertEqual("sweetyshivzz454@gmail.com", kwargs["user"])
        self.assertEqual("postgres", kwargs["dbname"])
        self.assertEqual("require", kwargs["sslmode"])
        self.assertEqual(15, kwargs["connect_timeout"])
        self.assertTrue(kwargs["autocommit"])
        self.assertIn("row_factory", kwargs)

    @patch("backend.nlsql.db.socket.create_connection")
    @patch("backend.nlsql.db.psycopg.connect")
    @patch("backend.nlsql.db.InteractiveBrowserCredential")
    @patch("backend.nlsql.db.DefaultAzureCredential")
    def test_connect_postgres_falls_back_to_interactive_browser_credential(
        self,
        default_credential_cls,
        interactive_credential_cls,
        connect_mock,
        socket_connect_mock,
    ) -> None:
        socket_connect_mock.return_value = MagicMock()
        default_credential = default_credential_cls.return_value
        default_credential.get_token.side_effect = RuntimeError("interaction required")
        interactive_credential = interactive_credential_cls.return_value
        interactive_credential.get_token.return_value = SimpleNamespace(token="browser-token")

        connect_postgres(self._settings())

        interactive_credential.get_token.assert_called_once_with(
            "https://ossrdbms-aad.database.windows.net/.default"
        )
        kwargs = connect_mock.call_args.kwargs
        self.assertEqual("browser-token", kwargs["password"])

    @patch.dict(os.environ, {"AZURE_TENANT_ID": "tenant-guid"}, clear=False)
    @patch("backend.nlsql.db.socket.create_connection")
    @patch("backend.nlsql.db.psycopg.connect")
    @patch("backend.nlsql.db.DefaultAzureCredential")
    def test_connect_postgres_passes_configured_tenant_to_default_credential(
        self,
        default_credential_cls,
        connect_mock,
        socket_connect_mock,
    ) -> None:
        socket_connect_mock.return_value = MagicMock()
        credential = default_credential_cls.return_value
        credential.get_token.return_value = SimpleNamespace(token="aad-token")

        connect_postgres(self._settings())

        default_credential_cls.assert_called_once_with(
            broker_tenant_id="tenant-guid",
            interactive_browser_tenant_id="tenant-guid",
            shared_cache_tenant_id="tenant-guid",
            visual_studio_code_tenant_id="tenant-guid",
        )
        self.assertEqual("aad-token", connect_mock.call_args.kwargs["password"])

    @patch.dict(os.environ, {"PGPASSWORD": "manual-token"}, clear=False)
    @patch("backend.nlsql.db.socket.create_connection")
    @patch("backend.nlsql.db.psycopg.connect")
    @patch("backend.nlsql.db.DefaultAzureCredential")
    def test_connect_postgres_prefers_explicit_pgpassword(
        self,
        default_credential_cls,
        connect_mock,
        socket_connect_mock,
    ) -> None:
        socket_connect_mock.return_value = MagicMock()
        connect_postgres(self._settings())

        default_credential_cls.assert_not_called()
        self.assertEqual("manual-token", connect_mock.call_args.kwargs["password"])

    @patch("backend.nlsql.db.socket.create_connection")
    @patch("backend.nlsql.db.psycopg.connect")
    @patch("backend.nlsql.db.DefaultAzureCredential")
    def test_connect_postgres_raises_actionable_error_when_socket_preflight_fails(
        self,
        default_credential_cls,
        connect_mock,
        socket_connect_mock,
    ) -> None:
        socket_connect_mock.side_effect = TimeoutError("timed out")

        with self.assertRaisesRegex(RuntimeError, "Network path to PostgreSQL is not reachable"):
            connect_postgres(self._settings())

        default_credential_cls.assert_not_called()
        connect_mock.assert_not_called()




