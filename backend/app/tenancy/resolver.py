from __future__ import annotations

from backend.app.tenancy.context import TenantRuntimeContext
from backend.app.tenancy.registry import tenant_runtime_registry
from backend.config import AppConfig, load_app_config


def _fallback_runtime_context(tenant_key: str, settings: AppConfig | None = None) -> TenantRuntimeContext:
    active_settings = settings or load_app_config(tenant_id_override=tenant_key)
    return TenantRuntimeContext(
        tenant_key=tenant_key,
        tenant_status="active",
        pg_host=active_settings.pg_host,
        pg_port=active_settings.pg_port,
        pg_database=active_settings.pg_database,
        pg_user=active_settings.pg_user,
        pg_password=active_settings.pg_password,
        pg_sslmode=active_settings.pg_sslmode,
        pg_connect_timeout=active_settings.pg_connect_timeout,
        neo4j_uri=active_settings.neo4j_uri,
        neo4j_username=active_settings.neo4j_username,
        neo4j_password=active_settings.neo4j_password,
        neo4j_database=active_settings.neo4j_database,
    )


def resolve_tenant_runtime(tenant_key: str, settings: AppConfig | None = None) -> TenantRuntimeContext:
    existing = tenant_runtime_registry.get(tenant_key)
    if existing is not None:
        return existing
    return tenant_runtime_registry.register(_fallback_runtime_context(tenant_key, settings))
