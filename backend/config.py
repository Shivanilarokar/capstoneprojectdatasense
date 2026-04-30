"""Central project configuration loaded from .env at repository root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
INGESTION_DATA_ROOT = DATA_ROOT / "ingestion"
SEC_DATA_ROOT = INGESTION_DATA_ROOT / "sec"
SEC_EDGAR_ROOT = SEC_DATA_ROOT / "edgar"
PAGEINDEX_DATA_ROOT = DATA_ROOT / "pageindex"
OBSERVABILITY_ROOT = DATA_ROOT / "observability"


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _env_csv_tuple(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    values: list[str] = []
    for item in raw.split(","):
        normalized = item.strip()
        if normalized and normalized not in values:
            values.append(normalized)
    return tuple(values)


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration shared by PageIndex, Graph RAG, and orchestration."""

    project_root: Path
    openai_api_key: str
    openai_model: str
    pageindex_api_key: str
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    graph_tenant_id: str
    sanctions_audit_log: Path
    pg_host: str
    pg_user: str
    pg_port: int
    pg_database: str
    pg_sslmode: str
    pg_connect_timeout: int
    azure_postgres_scope: str
    pg_password: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8002/google/callback"
    google_frontend_redirect_uri: str = "http://127.0.0.1:5173/auth/callback"
    google_scope: str = "openid email profile"
    google_admin_emails: tuple[str, ...] = ()
    app_auth_secret: str = ""
    app_auth_audience: str = "supplychainnexus-api"
    app_auth_issuer: str = "supplychainnexus-google-sso"
    google_default_tenant_key: str = "default"
    cors_allowed_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    control_plane_database_url: str = ""
    tenant_postgres_admin_host: str = ""
    tenant_postgres_admin_port: int = 5432
    tenant_postgres_admin_user: str = ""
    tenant_postgres_admin_password: str = ""
    tenant_postgres_admin_sslmode: str = "require"
    tenant_neo4j_admin_uri: str = ""
    tenant_neo4j_admin_username: str = ""
    tenant_neo4j_admin_password: str = ""
    pageindex_sections_json: Path = SEC_DATA_ROOT / "extracted_10k_sections.json"
    pageindex_docs_dir: Path = PAGEINDEX_DATA_ROOT / "docs"
    pageindex_workspace_dir: Path = PAGEINDEX_DATA_ROOT / "workspace"
    pageindex_output_dir: Path = PAGEINDEX_DATA_ROOT / "output"
    observability_dir: Path = OBSERVABILITY_ROOT
    alert_event_log: Path = OBSERVABILITY_ROOT / "alerts.jsonl"
    langsmith_project: str = ""
    langsmith_tracing: bool = False

    def with_tenant(self, tenant_id: str | None) -> "AppConfig":
        """Return a copy with tenant override."""
        chosen = (tenant_id or "").strip() or self.graph_tenant_id
        return AppConfig(
            project_root=self.project_root,
            openai_api_key=self.openai_api_key,
            openai_model=self.openai_model,
            pageindex_api_key=self.pageindex_api_key,
            neo4j_uri=self.neo4j_uri,
            neo4j_username=self.neo4j_username,
            neo4j_password=self.neo4j_password,
            neo4j_database=self.neo4j_database,
            graph_tenant_id=chosen,
            sanctions_audit_log=self.sanctions_audit_log,
            pg_host=self.pg_host,
            pg_user=self.pg_user,
            pg_port=self.pg_port,
            pg_database=self.pg_database,
            pg_sslmode=self.pg_sslmode,
            pg_connect_timeout=self.pg_connect_timeout,
            azure_postgres_scope=self.azure_postgres_scope,
            pg_password=self.pg_password,
            google_client_id=self.google_client_id,
            google_client_secret=self.google_client_secret,
            google_redirect_uri=self.google_redirect_uri,
            google_frontend_redirect_uri=self.google_frontend_redirect_uri,
            google_scope=self.google_scope,
            google_admin_emails=self.google_admin_emails,
            app_auth_secret=self.app_auth_secret,
            app_auth_audience=self.app_auth_audience,
            app_auth_issuer=self.app_auth_issuer,
            google_default_tenant_key=self.google_default_tenant_key,
            cors_allowed_origins=self.cors_allowed_origins,
            control_plane_database_url=self.control_plane_database_url,
            tenant_postgres_admin_host=self.tenant_postgres_admin_host,
            tenant_postgres_admin_port=self.tenant_postgres_admin_port,
            tenant_postgres_admin_user=self.tenant_postgres_admin_user,
            tenant_postgres_admin_password=self.tenant_postgres_admin_password,
            tenant_postgres_admin_sslmode=self.tenant_postgres_admin_sslmode,
            tenant_neo4j_admin_uri=self.tenant_neo4j_admin_uri,
            tenant_neo4j_admin_username=self.tenant_neo4j_admin_username,
            tenant_neo4j_admin_password=self.tenant_neo4j_admin_password,
            pageindex_sections_json=self.pageindex_sections_json,
            pageindex_docs_dir=self.pageindex_docs_dir,
            pageindex_workspace_dir=self.pageindex_workspace_dir,
            pageindex_output_dir=self.pageindex_output_dir,
            observability_dir=self.observability_dir,
            alert_event_log=self.alert_event_log,
            langsmith_project=self.langsmith_project,
            langsmith_tracing=self.langsmith_tracing,
        )


def load_app_config(tenant_id_override: str | None = None) -> AppConfig:
    """Load central app configuration from environment variables."""
    load_dotenv()
    tenant = (tenant_id_override or os.getenv("GRAPH_TENANT_ID", "default")).strip() or "default"

    audit_default = PROJECT_ROOT / "backend" / "graphrag" / "audit_logs" / "sanctions_screening.jsonl"
    return AppConfig(
        project_root=PROJECT_ROOT,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        pageindex_api_key=os.getenv("PAGEINDEX_API_KEY", "").strip(),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687").strip(),
        neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j").strip(),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "").strip(),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j").strip(),
        graph_tenant_id=tenant,
        sanctions_audit_log=Path(os.getenv("SANCTIONS_AUDIT_LOG", str(audit_default))),
        pg_host=os.getenv("PGHOST", "").strip(),
        pg_user=os.getenv("PGUSER", "").strip(),
        pg_port=int(os.getenv("PGPORT", "5432")),
        pg_database=os.getenv("PGDATABASE", "postgres").strip(),
        pg_sslmode=os.getenv("PGSSLMODE", "require").strip(),
        pg_connect_timeout=max(1, int(os.getenv("PGCONNECT_TIMEOUT", "15"))),
        azure_postgres_scope=os.getenv(
            "AZURE_POSTGRES_SCOPE",
            "https://ossrdbms-aad.database.windows.net/.default",
        ).strip(),
        pg_password=os.getenv("PGPASSWORD", "").strip(),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        google_redirect_uri=os.getenv(
            "GOOGLE_REDIRECT_URI",
            "http://127.0.0.1:8002/google/callback",
        ).strip(),
        google_frontend_redirect_uri=os.getenv(
            "GOOGLE_FRONTEND_REDIRECT_URI",
            "http://127.0.0.1:5173/auth/callback",
        ).strip(),
        google_scope=os.getenv("GOOGLE_SCOPE", "openid email profile").strip(),
        google_admin_emails=tuple(value.lower() for value in _env_csv_tuple("GOOGLE_ADMIN_EMAILS")),
        app_auth_secret=os.getenv("APP_AUTH_SECRET", "").strip(),
        app_auth_audience=os.getenv("APP_AUTH_AUDIENCE", "supplychainnexus-api").strip(),
        app_auth_issuer=os.getenv("APP_AUTH_ISSUER", "supplychainnexus-google-sso").strip(),
        google_default_tenant_key=os.getenv("GOOGLE_DEFAULT_TENANT_KEY", tenant).strip() or tenant,
        cors_allowed_origins=_env_csv_tuple("CORS_ALLOWED_ORIGINS")
        or ("http://127.0.0.1:5173", "http://localhost:5173"),
        control_plane_database_url=os.getenv("CONTROL_PLANE_DATABASE_URL", "").strip(),
        tenant_postgres_admin_host=os.getenv("TENANT_POSTGRES_ADMIN_HOST", "").strip(),
        tenant_postgres_admin_port=max(1, int(os.getenv("TENANT_POSTGRES_ADMIN_PORT", "5432"))),
        tenant_postgres_admin_user=os.getenv("TENANT_POSTGRES_ADMIN_USER", "").strip(),
        tenant_postgres_admin_password=os.getenv("TENANT_POSTGRES_ADMIN_PASSWORD", "").strip(),
        tenant_postgres_admin_sslmode=os.getenv("TENANT_POSTGRES_ADMIN_SSLMODE", "require").strip(),
        tenant_neo4j_admin_uri=os.getenv("TENANT_NEO4J_ADMIN_URI", "").strip(),
        tenant_neo4j_admin_username=os.getenv("TENANT_NEO4J_ADMIN_USERNAME", "").strip(),
        tenant_neo4j_admin_password=os.getenv("TENANT_NEO4J_ADMIN_PASSWORD", "").strip(),
        pageindex_sections_json=Path(
            os.getenv("PAGEINDEX_SECTIONS_JSON", str(SEC_DATA_ROOT / "extracted_10k_sections.json"))
        ),
        pageindex_docs_dir=Path(
            os.getenv("PAGEINDEX_DOCS_DIR", str(PAGEINDEX_DATA_ROOT / "docs"))
        ),
        pageindex_workspace_dir=Path(
            os.getenv("PAGEINDEX_WORKSPACE_DIR", str(PAGEINDEX_DATA_ROOT / "workspace"))
        ),
        pageindex_output_dir=Path(
            os.getenv("PAGEINDEX_OUTPUT_DIR", str(PAGEINDEX_DATA_ROOT / "output"))
        ),
        observability_dir=Path(
            os.getenv("OBSERVABILITY_DIR", str(OBSERVABILITY_ROOT))
        ),
        alert_event_log=Path(
            os.getenv("ALERT_EVENT_LOG", str(OBSERVABILITY_ROOT / "alerts.jsonl"))
        ),
        langsmith_project=os.getenv("LANGSMITH_PROJECT", "").strip(),
        langsmith_tracing=os.getenv("LANGSMITH_TRACING", "").strip().lower() in {"1", "true", "yes", "on"},
    )



