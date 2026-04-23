"""Central project configuration loaded from .env at repository root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data"
INGESTION_DATA_ROOT = DATA_ROOT / "ingestion"
SEC_DATA_ROOT = INGESTION_DATA_ROOT / "sec"
SEC_EDGAR_ROOT = SEC_DATA_ROOT / "edgar"
PAGEINDEX_DATA_ROOT = DATA_ROOT / "pageindex"
OBSERVABILITY_ROOT = DATA_ROOT / "observability"


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
    azure_postgres_scope: str
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
            azure_postgres_scope=self.azure_postgres_scope,
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

    audit_default = PROJECT_ROOT / "src" / "graphrag" / "audit_logs" / "sanctions_screening.jsonl"
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
        azure_postgres_scope=os.getenv(
            "AZURE_POSTGRES_SCOPE",
            "https://ossrdbms-aad.database.windows.net/.default",
        ).strip(),
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
