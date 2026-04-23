from __future__ import annotations

import os
from contextlib import contextmanager
from types import SimpleNamespace

from config import AppConfig

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = SimpleNamespace(connect=None)

    def dict_row(*_args, **_kwargs):
        return None

try:
    from azure.identity import DefaultAzureCredential
    from azure.identity import InteractiveBrowserCredential
except ImportError:
    class DefaultAzureCredential:  # type: ignore[override]
        def get_token(self, *_args, **_kwargs):
            raise RuntimeError("azure-identity is required for PostgreSQL Azure AD authentication.")

    class InteractiveBrowserCredential:  # type: ignore[override]
        def get_token(self, *_args, **_kwargs):
            raise RuntimeError("azure-identity is required for interactive PostgreSQL authentication.")


def _tenant_credential_kwargs() -> dict[str, str]:
    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
    if not tenant_id:
        return {}
    return {
        "broker_tenant_id": tenant_id,
        "interactive_browser_tenant_id": tenant_id,
        "shared_cache_tenant_id": tenant_id,
        "visual_studio_code_tenant_id": tenant_id,
    }


def _configured_pgpassword() -> str | None:
    password = os.getenv("PGPASSWORD", "").strip()
    return password or None


def _acquire_postgres_token(scope: str) -> str:
    configured_password = _configured_pgpassword()
    if configured_password:
        return configured_password

    tenant_kwargs = _tenant_credential_kwargs()
    default_credential = DefaultAzureCredential(**tenant_kwargs)
    try:
        return default_credential.get_token(scope).token
    except Exception:
        interactive_tenant_id = tenant_kwargs.get("interactive_browser_tenant_id")
        interactive_credential = (
            InteractiveBrowserCredential(tenant_id=interactive_tenant_id)
            if interactive_tenant_id
            else InteractiveBrowserCredential()
        )
        return interactive_credential.get_token(scope).token


def connect_postgres(settings: AppConfig):
    connect_fn = getattr(psycopg, "connect", None)
    if connect_fn is None:
        raise RuntimeError("psycopg is required for PostgreSQL connections.")

    token = _acquire_postgres_token(settings.azure_postgres_scope)
    return connect_fn(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_database,
        user=settings.pg_user,
        password=token,
        sslmode=settings.pg_sslmode,
        autocommit=True,
        row_factory=dict_row,
    )


@contextmanager
def open_readonly_cursor(conn):
    with conn.cursor() as cur:
        cur.execute("SET default_transaction_read_only = on")
        yield cur
