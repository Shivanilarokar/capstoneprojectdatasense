import os
from unittest import TestCase
from unittest.mock import patch

from backend.config import load_app_config


class ConfigTests(TestCase):
    @patch.dict(
        os.environ,
        {
            "PGHOST": "postgescapstoneproject.postgres.database.azure.com",
            "PGUSER": "sweetyshivzz454@gmail.com",
            "PGPORT": "5432",
            "PGDATABASE": "postgres",
        },
        clear=False,
    )
    def test_load_app_config_reads_postgres_runtime_settings(self) -> None:
        settings = load_app_config(tenant_id_override="tenant-dev")

        self.assertEqual("postgescapstoneproject.postgres.database.azure.com", settings.pg_host)
        self.assertEqual("sweetyshivzz454@gmail.com", settings.pg_user)
        self.assertEqual(5432, settings.pg_port)
        self.assertEqual("postgres", settings.pg_database)
        self.assertEqual("require", settings.pg_sslmode)
        self.assertEqual(15, settings.pg_connect_timeout)
        self.assertEqual(
            "https://ossrdbms-aad.database.windows.net/.default",
            settings.azure_postgres_scope,
        )

    @patch.dict(
        os.environ,
        {
            "APP_AUTH_SECRET": "separate-app-auth-secret",
            "APP_AUTH_AUDIENCE": "supplychainnexus-api",
            "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
            "GOOGLE_ADMIN_EMAILS": "admin@example.com,ops@example.com",
        },
        clear=False,
    )
    def test_load_app_config_reads_app_jwt_settings(self) -> None:
        settings = load_app_config()

        self.assertEqual("separate-app-auth-secret", settings.app_auth_secret)
        self.assertEqual("supplychainnexus-api", settings.app_auth_audience)
        self.assertEqual("supplychainnexus-google-sso", settings.app_auth_issuer)
        self.assertEqual(("admin@example.com", "ops@example.com"), settings.google_admin_emails)

    @patch.dict(
        os.environ,
        {
            "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
        },
        clear=False,
    )
    def test_load_app_config_reads_cors_allowed_origins(self) -> None:
        settings = load_app_config()

        self.assertEqual(
            ("http://127.0.0.1:5173", "http://localhost:5173"),
            settings.cors_allowed_origins,
        )

    @patch.dict(
        os.environ,
        {
            "PAGEINDEX_SECTIONS_JSON": "/srv/scn/sections.json",
            "PAGEINDEX_DOCS_DIR": "/srv/scn/docs",
            "PAGEINDEX_WORKSPACE_DIR": "/srv/scn/workspace",
            "PAGEINDEX_OUTPUT_DIR": "/srv/scn/output",
        },
        clear=False,
    )
    def test_load_app_config_reads_pageindex_paths(self) -> None:
        settings = load_app_config()

        self.assertEqual("/srv/scn/sections.json", settings.pageindex_sections_json.as_posix())
        self.assertEqual("/srv/scn/docs", settings.pageindex_docs_dir.as_posix())
        self.assertEqual("/srv/scn/workspace", settings.pageindex_workspace_dir.as_posix())
        self.assertEqual("/srv/scn/output", settings.pageindex_output_dir.as_posix())



