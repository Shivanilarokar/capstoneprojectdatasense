from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantRuntimeContext:
    tenant_key: str
    tenant_status: str
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str
    pg_sslmode: str
    pg_connect_timeout: int
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
