from __future__ import annotations

from unittest import TestCase

from backend.app.auth.principal import CurrentPrincipal
from backend.app.tenancy.context import TenantRuntimeContext


class TenantResolutionTests(TestCase):
    def test_runtime_context_builds_from_principal(self) -> None:
        principal = CurrentPrincipal(
            subject="user-1",
            email="user@example.com",
            roles=("user",),
            tenant_key="tenant-acme",
            token_claims={},
        )
        context = TenantRuntimeContext(
            tenant_key=principal.tenant_key,
            tenant_status="active",
            pg_host="tenant.postgres.database.azure.com",
            pg_port=5432,
            pg_database="tenant_acme",
            pg_user="tenant_user",
            pg_password="secret",
            pg_sslmode="require",
            pg_connect_timeout=15,
            neo4j_uri="neo4j+s://tenant.databases.neo4j.io",
            neo4j_username="tenant",
            neo4j_password="secret",
            neo4j_database="tenant",
        )

        self.assertEqual("tenant-acme", context.tenant_key)
