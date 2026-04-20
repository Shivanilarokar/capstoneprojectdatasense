import os
from unittest import TestCase
from unittest.mock import patch

from config import load_app_config


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
        self.assertEqual(
            "https://ossrdbms-aad.database.windows.net/.default",
            settings.azure_postgres_scope,
        )
