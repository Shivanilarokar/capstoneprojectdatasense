# SupplyChainNexus Product Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the current CLI-driven Python routes into a `backend/` FastAPI product backend, physically move all Python modules from `src/` into `backend/`, add Entra External ID auth plus tenant control-plane support, and build a `frontend/` Vite + React + TypeScript product UI with query, graph, and admin experiences.

**Architecture:** Keep the existing route engines modular, but physically relocate them into `backend/` and expose them only through FastAPI service adapters. Build a separate `frontend/` SPA that authenticates through Entra External ID, calls one orchestrator-backed query API, renders graph data from dedicated graph endpoints, and gates admin read-only views by role.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, psycopg, neo4j, OpenAI, LangGraph, python-dotenv, requests, Vite, React, TypeScript, react-router-dom, react-oidc-context, oidc-client-ts, Cytoscape.js

---

## Target Layout

By the end of implementation, the repo should look like this:

```text
backend/
  __init__.py
  main.py
  config.py
  app/
    __init__.py
    api/
      __init__.py
      deps.py
      auth.py
      tenants.py
      query.py
      graph.py
      admin.py
      system.py
      models/
        __init__.py
        auth.py
        tenant.py
        query.py
        graph.py
        admin.py
        system.py
    auth/
      __init__.py
      entra.py
      principal.py
    control_plane/
      __init__.py
      db.py
      schema.py
      repository.py
      provisioning.py
    services/
      __init__.py
      orchestrator_service.py
      graph_service.py
      admin_service.py
      tenant_service.py
    tenancy/
      __init__.py
      context.py
      registry.py
      resolver.py
  evaluation/
  generation/
  graphrag/
  ingestion/
  nlsql/
  observability/
  orchestrator/
  pageindex/
  sanctions/
  tests/
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    App.tsx
    routes/
    app/
    lib/
    components/
    features/
      auth/
      query/
      graph/
      admin/
main.py
pyproject.toml
requirements.txt
README.md
```

## File Move Map

### Python packages to move from `src/` to `backend/`

- `src/evaluation` -> `backend/evaluation`
- `src/generation` -> `backend/generation`
- `src/graphrag` -> `backend/graphrag`
- `src/ingestion` -> `backend/ingestion`
- `src/nlsql` -> `backend/nlsql`
- `src/observability` -> `backend/observability`
- `src/orchestrator` -> `backend/orchestrator`
- `src/pageindex` -> `backend/pageindex`
- `src/sanctions` -> `backend/sanctions`
- `config.py` -> `backend/config.py`

### Python tests to move under `backend/tests/`

- `tests/evaluation` -> `backend/tests/evaluation`
- `tests/graphrag` -> `backend/tests/graphrag`
- `tests/ingestion` -> `backend/tests/ingestion`
- `tests/nlsql` -> `backend/tests/nlsql`
- `tests/orchestrator` -> `backend/tests/orchestrator`
- `tests/pageindex` -> `backend/tests/pageindex`
- `tests/sanctions` -> `backend/tests/sanctions`
- `tests/test_config.py` -> `backend/tests/test_config.py`
- `tests/test_dependencies.py` -> `backend/tests/test_dependencies.py`

### CLI surface to retire

- `run_agentic_router.py`
- `run_competition_benchmark.py`
- `run_graphrag_pipeline.py`
- `run_graphrag_query.py`
- `run_graphrag_topology.py`
- `run_ingestion.py`
- `run_nlsql_query.py`
- `run_pageindex_pipeline.py`
- `run_sanctions_query.py`
- `backend/*/cli.py`

## Task 1: Establish `backend/` As the Python Package Root

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_package_layout.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Move: `config.py`
- Move: `src/generation/*`
- Move: `src/observability/*`
- Move: `tests/test_config.py`
- Move: `tests/test_dependencies.py`

- [ ] **Step 1: Write the failing package-layout test**

```python
# backend/tests/test_package_layout.py
from __future__ import annotations


def test_backend_package_imports() -> None:
    from backend.config import load_app_config
    from backend.generation.generation import LLMConfig
    from backend.observability.logging import emit_trace_event

    assert callable(load_app_config)
    assert LLMConfig.__name__ == "LLMConfig"
    assert callable(emit_trace_event)
```

- [ ] **Step 2: Run the test to verify it fails before the move**

Run:

```bash
pytest backend/tests/test_package_layout.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend'
```

- [ ] **Step 3: Move shared foundation modules and create the package root**

Run:

```powershell
New-Item -ItemType Directory -Force backend, backend\tests | Out-Null
Move-Item config.py backend\config.py
Move-Item src\generation backend\generation
Move-Item src\observability backend\observability
Move-Item tests\test_config.py backend\tests\test_config.py
Move-Item tests\test_dependencies.py backend\tests\test_dependencies.py
Set-Content backend\__init__.py ""
Set-Content backend\tests\__init__.py ""
```

Update `pyproject.toml` so tests resolve from `backend/`:

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
pythonpath = ["."]
```

- [ ] **Step 4: Run the package-layout test again**

Run:

```bash
pytest backend/tests/test_package_layout.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/__init__.py backend/tests/__init__.py backend/tests/test_package_layout.py backend/config.py backend/generation backend/observability backend/tests/test_config.py backend/tests/test_dependencies.py pyproject.toml
git commit -m "refactor: establish backend package root"
```

## Task 2: Move the Existing Route Packages and Repair Imports

**Files:**
- Move: `src/evaluation/*` -> `backend/evaluation/*`
- Move: `src/graphrag/*` -> `backend/graphrag/*`
- Move: `src/ingestion/*` -> `backend/ingestion/*`
- Move: `src/nlsql/*` -> `backend/nlsql/*`
- Move: `src/orchestrator/*` -> `backend/orchestrator/*`
- Move: `src/pageindex/*` -> `backend/pageindex/*`
- Move: `src/sanctions/*` -> `backend/sanctions/*`
- Move: `tests/evaluation/*` -> `backend/tests/evaluation/*`
- Move: `tests/graphrag/*` -> `backend/tests/graphrag/*`
- Move: `tests/ingestion/*` -> `backend/tests/ingestion/*`
- Move: `tests/nlsql/*` -> `backend/tests/nlsql/*`
- Move: `tests/orchestrator/*` -> `backend/tests/orchestrator/*`
- Move: `tests/pageindex/*` -> `backend/tests/pageindex/*`
- Move: `tests/sanctions/*` -> `backend/tests/sanctions/*`
- Modify: all Python imports that currently read `from config import ...`

- [ ] **Step 1: Write a failing import sweep test for the moved domain packages**

```python
# backend/tests/test_domain_imports.py
from __future__ import annotations


def test_domain_packages_import() -> None:
    from backend.orchestrator.agent import AgenticOptions
    from backend.graphrag.query import run_graph_query
    from backend.nlsql.query import run_nlsql_query
    from backend.pageindex.pipeline import run_pipeline
    from backend.sanctions.query import run_sanctions_query
    from backend.ingestion.ingestion_cli import run_ingestion

    assert AgenticOptions.__name__ == "AgenticOptions"
    assert callable(run_graph_query)
    assert callable(run_nlsql_query)
    assert callable(run_pipeline)
    assert callable(run_sanctions_query)
    assert callable(run_ingestion)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest backend/tests/test_domain_imports.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.orchestrator'
```

- [ ] **Step 3: Move packages and update imports**

Run:

```powershell
Move-Item src\evaluation backend\evaluation
Move-Item src\graphrag backend\graphrag
Move-Item src\ingestion backend\ingestion
Move-Item src\nlsql backend\nlsql
Move-Item src\orchestrator backend\orchestrator
Move-Item src\pageindex backend\pageindex
Move-Item src\sanctions backend\sanctions
Move-Item tests\evaluation backend\tests\evaluation
Move-Item tests\graphrag backend\tests\graphrag
Move-Item tests\ingestion backend\tests\ingestion
Move-Item tests\nlsql backend\tests\nlsql
Move-Item tests\orchestrator backend\tests\orchestrator
Move-Item tests\pageindex backend\tests\pageindex
Move-Item tests\sanctions backend\tests\sanctions
```

Update imports in moved modules. Example:

```python
# backend/orchestrator/agent.py
from backend.config import AppConfig
from backend.generation.generation import LLMConfig, chat_json, chat_text
from backend.observability import emit_alert_event, emit_trace_event, write_checkpoint
```

```python
# backend/graphrag/query.py
from backend.generation.generation import LLMConfig, chat_json, chat_text
from backend.config import AppConfig
```

```python
# backend/pageindex/pipeline.py
from backend.config import load_app_config
```

Use a repo-wide import sweep:

```powershell
Get-ChildItem backend -Recurse -Filter *.py | ForEach-Object {
  (Get-Content $_.FullName) `
    -replace '^from config import', 'from backend.config import' `
    -replace '^from generation', 'from backend.generation' `
    -replace '^from observability', 'from backend.observability' |
    Set-Content $_.FullName
}
```

- [ ] **Step 4: Run the import sweep and representative package tests**

Run:

```bash
pytest backend/tests/test_domain_imports.py backend/tests/orchestrator/test_graph.py backend/tests/graphrag/test_pipeline.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend backend/tests pyproject.toml
git commit -m "refactor: move route packages into backend"
```

## Task 3: Add the FastAPI App Skeleton and System Endpoints

**Files:**
- Create: `backend/main.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/system.py`
- Create: `backend/app/api/models/__init__.py`
- Create: `backend/app/api/models/system.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Create: `backend/tests/api/test_system_api.py`

- [ ] **Step 1: Write the failing API health test**

```python
# backend/tests/api/test_system_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/system/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest backend/tests/api/test_system_api.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.main'
```

- [ ] **Step 3: Implement the FastAPI app shell**

Add the new runtime dependencies:

```toml
[project]
dependencies = [
  "fastapi==0.122.0",
  "uvicorn==0.38.0",
  "httpx==0.28.1",
  "python-jose[cryptography]==3.5.0",
]
```

Create the API shell:

```python
# backend/app/api/system.py
from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}
```

```python
# backend/main.py
from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.system import router as system_router


def create_app() -> FastAPI:
    app = FastAPI(title="SupplyChainNexus API", version="0.1.0")
    app.include_router(system_router)
    return app


app = create_app()
```

- [ ] **Step 4: Run the system endpoint test**

Run:

```bash
pytest backend/tests/api/test_system_api.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/app backend/tests/api/test_system_api.py pyproject.toml requirements.txt
git commit -m "feat: add fastapi application shell"
```

## Task 4: Add Entra External ID Auth and Role Dependencies

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/principal.py`
- Create: `backend/app/auth/entra.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/app/api/models/auth.py`
- Modify: `backend/config.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/tests/auth/test_auth_dependencies.py`

- [ ] **Step 1: Write failing tests for token and role dependencies**

```python
# backend/tests/auth/test_auth_dependencies.py
from __future__ import annotations

from backend.app.auth.principal import CurrentPrincipal


def test_principal_role_check() -> None:
    principal = CurrentPrincipal(
        subject="user-1",
        email="user@example.com",
        roles=("user",),
        tenant_key="tenant-1",
        token_claims={},
    )
    assert principal.has_role("user") is True
    assert principal.has_role("admin") is False
```

- [ ] **Step 2: Run the auth dependency test to verify it fails**

Run:

```bash
pytest backend/tests/auth/test_auth_dependencies.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.app.auth'
```

- [ ] **Step 3: Implement auth models and bearer-token validation hooks**

Extend config with Entra settings:

```python
# backend/config.py
    entra_authority: str
    entra_client_id: str
    entra_api_audience: str
    entra_jwks_url: str
```

Create the principal model:

```python
# backend/app/auth/principal.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CurrentPrincipal:
    subject: str
    email: str
    roles: tuple[str, ...]
    tenant_key: str
    token_claims: dict[str, Any]

    def has_role(self, role: str) -> bool:
        return role in self.roles
```

Create the dependency hooks:

```python
# backend/app/api/deps.py
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.auth.entra import validate_access_token
from backend.app.auth.principal import CurrentPrincipal


bearer_scheme = HTTPBearer(auto_error=True)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentPrincipal:
    return validate_access_token(credentials.credentials)


def require_admin(principal: CurrentPrincipal = Depends(get_current_principal)) -> CurrentPrincipal:
    if not principal.has_role("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return principal
```

- [ ] **Step 4: Run auth tests**

Run:

```bash
pytest backend/tests/auth/test_auth_dependencies.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth backend/app/api/auth.py backend/app/api/deps.py backend/app/api/models/auth.py backend/tests/auth/test_auth_dependencies.py backend/config.py
git commit -m "feat: add entra auth foundation"
```

## Task 5: Add the Tenant Control Plane and Per-Tenant Runtime Resolution

**Files:**
- Create: `backend/app/control_plane/__init__.py`
- Create: `backend/app/control_plane/db.py`
- Create: `backend/app/control_plane/schema.py`
- Create: `backend/app/control_plane/repository.py`
- Create: `backend/app/control_plane/provisioning.py`
- Create: `backend/app/tenancy/__init__.py`
- Create: `backend/app/tenancy/context.py`
- Create: `backend/app/tenancy/registry.py`
- Create: `backend/app/tenancy/resolver.py`
- Create: `backend/app/api/tenants.py`
- Create: `backend/app/api/models/tenant.py`
- Modify: `backend/config.py`
- Create: `backend/tests/tenancy/test_tenant_resolution.py`

- [ ] **Step 1: Write failing tests for tenant resolution**

```python
# backend/tests/tenancy/test_tenant_resolution.py
from __future__ import annotations

from backend.app.auth.principal import CurrentPrincipal
from backend.app.tenancy.context import TenantRuntimeContext


def test_runtime_context_builds_from_principal() -> None:
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
    assert context.tenant_key == "tenant-acme"
```

- [ ] **Step 2: Run the tenant-resolution test to verify it fails**

Run:

```bash
pytest backend/tests/tenancy/test_tenant_resolution.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.app.tenancy'
```

- [ ] **Step 3: Implement the control-plane and tenant-context primitives**

Add control-plane settings:

```python
# backend/config.py
    pg_password: str
    control_plane_database_url: str
    tenant_postgres_admin_host: str
    tenant_postgres_admin_port: int
    tenant_postgres_admin_user: str
    tenant_postgres_admin_password: str
    tenant_postgres_admin_sslmode: str
    tenant_neo4j_admin_uri: str
    tenant_neo4j_admin_username: str
    tenant_neo4j_admin_password: str
```

Create the tenant runtime context:

```python
# backend/app/tenancy/context.py
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
```

Create the schema bootstrap:

```python
# backend/app/control_plane/schema.py
TENANTS_SQL = """
CREATE TABLE IF NOT EXISTS tenants (
    tenant_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    pg_host TEXT NOT NULL,
    pg_port INTEGER NOT NULL,
    pg_database TEXT NOT NULL,
    pg_user TEXT NOT NULL,
    pg_password TEXT NOT NULL,
    pg_sslmode TEXT NOT NULL,
    neo4j_uri TEXT NOT NULL,
    neo4j_username TEXT NOT NULL,
    neo4j_password TEXT NOT NULL,
    neo4j_database TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""
```

Create the API router:

```python
# backend/app/api/tenants.py
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_principal
from backend.app.auth.principal import CurrentPrincipal


router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me")
def current_tenant(principal: CurrentPrincipal = Depends(get_current_principal)) -> dict[str, str]:
    return {"tenant_key": principal.tenant_key}
```

- [ ] **Step 4: Run tenancy tests**

Run:

```bash
pytest backend/tests/tenancy/test_tenant_resolution.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/control_plane backend/app/tenancy backend/app/api/tenants.py backend/app/api/models/tenant.py backend/tests/tenancy/test_tenant_resolution.py backend/config.py
git commit -m "feat: add tenant control plane foundation"
```

## Task 6: Wrap the Existing Orchestrator Behind `/query/*`

**Files:**
- Create: `backend/app/services/orchestrator_service.py`
- Create: `backend/app/api/query.py`
- Create: `backend/app/api/models/query.py`
- Modify: `backend/main.py`
- Modify: `backend/orchestrator/agent.py`
- Create: `backend/tests/api/test_query_api.py`

- [ ] **Step 1: Write the failing query endpoint test**

```python
# backend/tests/api/test_query_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_query_endpoint_exists() -> None:
    client = TestClient(app)
    response = client.post("/query/ask", json={"question": "Which states had the highest storm damage?"})
    assert response.status_code in {200, 401, 403}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest backend/tests/api/test_query_api.py -q
```

Expected:

```text
E   assert 404 in {200, 401, 403}
```

- [ ] **Step 3: Implement the query service and router**

Create the request/response models:

```python
# backend/app/api/models/query.py
from __future__ import annotations

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    selected_pipeline: str
    route_plan: dict
    warnings: list[str]
```

Create the service adapter:

```python
# backend/app/services/orchestrator_service.py
from __future__ import annotations

from backend.config import AppConfig
from backend.orchestrator.agent import AgenticOptions, run_agentic_query


def ask_supplychainnexus(settings: AppConfig, question: str, user_id: str, roles: tuple[str, ...]) -> dict:
    return run_agentic_query(
        settings=settings,
        question=question,
        user_id=user_id,
        options=AgenticOptions(user_roles=roles),
    )
```

Expose the API:

```python
# backend/app/api/query.py
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_principal, get_current_settings
from backend.app.api.models.query import QueryRequest
from backend.app.auth.principal import CurrentPrincipal
from backend.app.services.orchestrator_service import ask_supplychainnexus
from backend.config import AppConfig


router = APIRouter(prefix="/query", tags=["query"])


@router.post("/ask")
def ask(
    payload: QueryRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    settings: AppConfig = Depends(get_current_settings),
) -> dict:
    return ask_supplychainnexus(
        settings=settings,
        question=payload.question,
        user_id=principal.subject,
        roles=principal.roles,
    )
```

- [ ] **Step 4: Run the query endpoint test**

Run:

```bash
pytest backend/tests/api/test_query_api.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/orchestrator_service.py backend/app/api/query.py backend/app/api/models/query.py backend/tests/api/test_query_api.py backend/main.py
git commit -m "feat: expose orchestrator query endpoint"
```

## Task 7: Add `/graph/*`, `/admin/*`, and `/system/*` Product APIs

**Files:**
- Create: `backend/app/services/graph_service.py`
- Create: `backend/app/services/admin_service.py`
- Create: `backend/app/api/graph.py`
- Create: `backend/app/api/admin.py`
- Create: `backend/app/api/models/graph.py`
- Create: `backend/app/api/models/admin.py`
- Modify: `backend/main.py`
- Create: `backend/tests/api/test_graph_api.py`
- Create: `backend/tests/api/test_admin_api.py`

- [ ] **Step 1: Write failing graph and admin endpoint tests**

```python
# backend/tests/api/test_graph_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_graph_answer_endpoint_exists() -> None:
    client = TestClient(app)
    response = client.get("/graph/answer/query-1")
    assert response.status_code in {200, 401, 403, 404}
```

```python
# backend/tests/api/test_admin_api.py
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_admin_overview_endpoint_exists() -> None:
    client = TestClient(app)
    response = client.get("/admin/overview")
    assert response.status_code in {200, 401, 403}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest backend/tests/api/test_graph_api.py backend/tests/api/test_admin_api.py -q
```

Expected:

```text
E   assert 404 in {200, 401, 403, 404}
E   assert 404 in {200, 401, 403}
```

- [ ] **Step 3: Implement the graph and admin routers**

Create the graph endpoint:

```python
# backend/app/api/graph.py
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_principal
from backend.app.auth.principal import CurrentPrincipal


router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/answer/{query_id}")
def answer_graph(query_id: str, principal: CurrentPrincipal = Depends(get_current_principal)) -> dict:
    return {"query_id": query_id, "nodes": [], "edges": [], "mode": "answer"}


@router.get("/explorer")
def explorer(principal: CurrentPrincipal = Depends(get_current_principal)) -> dict:
    return {"nodes": [], "edges": [], "mode": "explorer"}
```

Create the admin endpoint:

```python
# backend/app/api/admin.py
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import require_admin
from backend.app.auth.principal import CurrentPrincipal


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def overview(principal: CurrentPrincipal = Depends(require_admin)) -> dict:
    return {"status": "ok", "cards": [], "tenants": []}
```

Wire them into the app:

```python
# backend/main.py
from backend.app.api.admin import router as admin_router
from backend.app.api.graph import router as graph_router
from backend.app.api.query import router as query_router
from backend.app.api.tenants import router as tenants_router
from backend.app.api.auth import router as auth_router
from backend.app.api.system import router as system_router
```

- [ ] **Step 4: Run graph and admin tests**

Run:

```bash
pytest backend/tests/api/test_graph_api.py backend/tests/api/test_admin_api.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/graph_service.py backend/app/services/admin_service.py backend/app/api/graph.py backend/app/api/admin.py backend/app/api/models/graph.py backend/app/api/models/admin.py backend/tests/api/test_graph_api.py backend/tests/api/test_admin_api.py backend/main.py
git commit -m "feat: add graph and admin api surface"
```

## Task 8: Retire the CLI Surface and Replace It With Product Entry Points

**Files:**
- Delete: `run_agentic_router.py`
- Delete: `run_competition_benchmark.py`
- Delete: `run_graphrag_pipeline.py`
- Delete: `run_graphrag_query.py`
- Delete: `run_graphrag_topology.py`
- Delete: `run_ingestion.py`
- Delete: `run_nlsql_query.py`
- Delete: `run_pageindex_pipeline.py`
- Delete: `run_sanctions_query.py`
- Delete: `backend/orchestrator/cli.py`
- Delete: `backend/graphrag/cli_pipeline.py`
- Delete: `backend/graphrag/cli_query.py`
- Delete: `backend/graphrag/cli_topology.py`
- Delete: `backend/nlsql/cli.py`
- Delete: `backend/pageindex/cli.py`
- Delete: `backend/sanctions/cli.py`
- Modify: `README.md`
- Create: `backend/tests/test_no_cli_surface.py`

- [ ] **Step 1: Write the failing no-CLI-surface test**

```python
# backend/tests/test_no_cli_surface.py
from __future__ import annotations

from pathlib import Path


def test_legacy_run_wrappers_are_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not (root / "run_agentic_router.py").exists()
    assert not (root / "run_graphrag_query.py").exists()
    assert not (root / "run_nlsql_query.py").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest backend/tests/test_no_cli_surface.py -q
```

Expected:

```text
E   assert not True
```

- [ ] **Step 3: Remove the user-facing CLI wrappers and rewrite README startup instructions**

Delete the runner scripts and retired CLI modules:

```powershell
Remove-Item run_agentic_router.py, run_competition_benchmark.py, run_graphrag_pipeline.py, run_graphrag_query.py, run_graphrag_topology.py, run_ingestion.py, run_nlsql_query.py, run_pageindex_pipeline.py, run_sanctions_query.py
Remove-Item backend\orchestrator\cli.py, backend\graphrag\cli_pipeline.py, backend\graphrag\cli_query.py, backend\graphrag\cli_topology.py, backend\nlsql\cli.py, backend\pageindex\cli.py, backend\sanctions\cli.py
```

Update the README to advertise only:

```md
## Product Runtime

Backend:

```bash
uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm run dev
```
```

- [ ] **Step 4: Run the no-CLI-surface test**

Run:

```bash
pytest backend/tests/test_no_cli_surface.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add README.md backend/tests/test_no_cli_surface.py
git rm run_agentic_router.py run_competition_benchmark.py run_graphrag_pipeline.py run_graphrag_query.py run_graphrag_topology.py run_ingestion.py run_nlsql_query.py run_pageindex_pipeline.py run_sanctions_query.py backend/orchestrator/cli.py backend/graphrag/cli_pipeline.py backend/graphrag/cli_query.py backend/graphrag/cli_topology.py backend/nlsql/cli.py backend/pageindex/cli.py backend/sanctions/cli.py
git commit -m "refactor: retire legacy cli surface"
```

## Task 9: Scaffold the `frontend/` Vite + React + TypeScript App

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/routes/router.tsx`
- Create: `frontend/src/app/layout/AppShell.tsx`
- Create: `frontend/src/app/styles.css`

- [ ] **Step 1: Write a failing frontend smoke test target**

Create the minimal build script target in `frontend/package.json` and expect it to fail because the app does not exist yet:

```json
{
  "name": "frontend",
  "private": true,
  "scripts": {
    "build": "vite build"
  }
}
```

- [ ] **Step 2: Run the frontend build to verify it fails**

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
Could not resolve entry module
```

- [ ] **Step 3: Scaffold the Vite React TypeScript app**

Run:

```bash
npm create vite@latest frontend -- --template react-ts
```

Add the base app shell:

```tsx
// frontend/src/App.tsx
import { RouterProvider } from "react-router-dom";
import { router } from "./routes/router";
import "./app/styles.css";

export default function App() {
  return <RouterProvider router={router} />;
}
```

```tsx
// frontend/src/routes/router.tsx
import { createBrowserRouter } from "react-router-dom";

export const router = createBrowserRouter([
  { path: "/", element: <div>SupplyChainNexus</div> },
]);
```

- [ ] **Step 4: Run the frontend build**

Run:

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

Expected:

```text
building for production
built in
```

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: scaffold frontend app"
```

## Task 10: Add Frontend Auth Bootstrap and App Shell

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/features/auth/AuthProvider.tsx`
- Create: `frontend/src/features/auth/RequireAuth.tsx`
- Create: `frontend/src/features/auth/RequireAdmin.tsx`
- Create: `frontend/src/lib/auth.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/routes/router.tsx`
- Create: `frontend/src/app/layout/Sidebar.tsx`
- Create: `frontend/src/app/layout/Header.tsx`
- Create: `frontend/src/app/layout/AppShell.tsx`

- [ ] **Step 1: Write the failing auth bootstrap expectation**

Add the intended dependencies:

```json
{
  "dependencies": {
    "react-oidc-context": "^3.3.0",
    "oidc-client-ts": "^3.2.0",
    "react-router-dom": "^7.6.2"
  }
}
```

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
Cannot find module './features/auth/AuthProvider'
```

- [ ] **Step 2: Run the build to verify it fails**

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
TS2307: Cannot find module './features/auth/AuthProvider'
```

- [ ] **Step 3: Implement the OIDC bootstrap and protected-shell wiring**

Use the React OIDC context pattern:

```tsx
// frontend/src/features/auth/AuthProvider.tsx
import { PropsWithChildren } from "react";
import { AuthProvider as OidcProvider } from "react-oidc-context";
import { WebStorageStateStore } from "oidc-client-ts";

const oidcConfig = {
  authority: import.meta.env.VITE_ENTRA_AUTHORITY,
  client_id: import.meta.env.VITE_ENTRA_CLIENT_ID,
  redirect_uri: `${window.location.origin}/auth/callback`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  scope: "openid profile email offline_access",
  automaticSilentRenew: true,
  userStore: new WebStorageStateStore({ store: window.localStorage }),
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};

export function AuthProvider({ children }: PropsWithChildren) {
  return <OidcProvider {...oidcConfig}>{children}</OidcProvider>;
}
```

```tsx
// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./features/auth/AuthProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
```

- [ ] **Step 4: Run the frontend build**

Run:

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

Expected:

```text
built in
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/src
git commit -m "feat: add frontend auth shell"
```

## Task 11: Build the Query Workspace and API Client

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/features/query/QueryPage.tsx`
- Create: `frontend/src/features/query/QueryForm.tsx`
- Create: `frontend/src/features/query/AnswerPanel.tsx`
- Create: `frontend/src/features/query/ProvenancePanel.tsx`
- Modify: `frontend/src/routes/router.tsx`

- [ ] **Step 1: Write the failing API client usage**

Wire the route first:

```tsx
// frontend/src/routes/router.tsx
{ path: "/query", element: <QueryPage /> }
```

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
TS2307: Cannot find module '../features/query/QueryPage'
```

- [ ] **Step 2: Run the build to verify it fails**

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
TS2307
```

- [ ] **Step 3: Implement the query page and API client**

```ts
// frontend/src/lib/api.ts
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
```

```tsx
// frontend/src/features/query/QueryPage.tsx
import { useState } from "react";
import { apiFetch } from "../../lib/api";

export function QueryPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<any>(null);

  async function submit() {
    const data = await apiFetch("/query/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    setResult(data);
  }

  return (
    <section>
      <h1>Ask SupplyChainNexus</h1>
      <textarea value={question} onChange={(e) => setQuestion(e.target.value)} />
      <button onClick={submit}>Run Query</button>
      <pre>{result ? JSON.stringify(result, null, 2) : "No result yet."}</pre>
    </section>
  );
}
```

- [ ] **Step 4: Run the frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
built in
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib frontend/src/features/query frontend/src/routes/router.tsx
git commit -m "feat: add query workspace"
```

## Task 12: Build the Graph Views and Read-Only Admin Dashboard

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/features/graph/GraphPage.tsx`
- Create: `frontend/src/features/graph/AnswerGraphTab.tsx`
- Create: `frontend/src/features/graph/ExplorerGraphTab.tsx`
- Create: `frontend/src/features/graph/CytoscapeCanvas.tsx`
- Create: `frontend/src/features/admin/AdminPage.tsx`
- Create: `frontend/src/features/admin/OverviewCards.tsx`
- Create: `frontend/src/features/admin/TenantTable.tsx`
- Modify: `frontend/src/routes/router.tsx`

- [ ] **Step 1: Write the failing graph dependency expectation**

Add the intended graph packages:

```json
{
  "dependencies": {
    "cytoscape": "^3.33.1",
    "react-cytoscapejs": "^2.0.0"
  }
}
```

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
TS2307: Cannot find module '../features/graph/GraphPage'
```

- [ ] **Step 2: Run the build to verify it fails**

Run:

```bash
npm --prefix frontend run build
```

Expected:

```text
TS2307
```

- [ ] **Step 3: Implement graph and admin pages**

Use the Cytoscape initialization pattern:

```tsx
// frontend/src/features/graph/CytoscapeCanvas.tsx
import CytoscapeComponent from "react-cytoscapejs";

type GraphProps = {
  elements: Array<{ data: Record<string, unknown> }>;
};

export function CytoscapeCanvas({ elements }: GraphProps) {
  return (
    <CytoscapeComponent
      elements={elements}
      style={{ width: "100%", height: "640px" }}
      layout={{ name: "cose" }}
      stylesheet={[
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "#334155",
            color: "#f8fafc",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#94a3b8",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
      ]}
    />
  );
}
```

```tsx
// frontend/src/features/admin/AdminPage.tsx
export function AdminPage() {
  return (
    <section>
      <h1>Admin Dashboard</h1>
      <p>Read-only tenant, health, and query summaries.</p>
    </section>
  );
}
```

- [ ] **Step 4: Run the frontend build**

Run:

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

Expected:

```text
built in
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/src/features/graph frontend/src/features/admin frontend/src/routes/router.tsx
git commit -m "feat: add graph and admin frontend views"
```

## Task 13: End-to-End Wiring, Tenant-Aware Settings Injection, and Final Verification

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/tenancy/resolver.py`
- Modify: `backend/app/services/orchestrator_service.py`
- Modify: `backend/app/services/graph_service.py`
- Modify: `backend/nlsql/db.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `main.py`
- Modify: `README.md`

- [ ] **Step 1: Write a tenant-aware API integration test**

```python
# backend/tests/api/test_tenant_aware_settings.py
from __future__ import annotations

from backend.app.tenancy.context import TenantRuntimeContext
from backend.app.tenancy.resolver import apply_tenant_runtime
from backend.config import load_app_config


def test_apply_tenant_runtime_overrides_connection_fields() -> None:
    base = load_app_config(tenant_id_override="tenant-base")
    context = TenantRuntimeContext(
        tenant_key="tenant-acme",
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
        neo4j_database="tenant-acme",
    )

    resolved = apply_tenant_runtime(base, context)

    assert resolved.graph_tenant_id == "tenant-acme"
    assert resolved.pg_host == "tenant.postgres.database.azure.com"
    assert resolved.pg_database == "tenant_acme"
    assert resolved.neo4j_uri == "neo4j+s://tenant.databases.neo4j.io"
    assert resolved.neo4j_database == "tenant-acme"
```

- [ ] **Step 2: Run the integration-focused backend and frontend checks**

Run:

```bash
pytest backend/tests/api -q
npm --prefix frontend run build
```

Expected:

```text
all tests passed
built in
```

- [ ] **Step 3: Implement tenant-aware settings resolution**

Create a dependency that turns a principal plus tenant metadata into the settings object consumed by the legacy route engines:

```python
# backend/app/api/deps.py
from backend.config import AppConfig, load_app_config


def get_current_settings(principal = Depends(get_current_principal)) -> AppConfig:
    base = load_app_config()
    context = resolve_tenant_runtime(principal.tenant_key)
    return apply_tenant_runtime(base, context)
```

Update the resolver and the Postgres connector so route execution uses tenant-specific credentials rather than global environment values. The key change in `backend/nlsql/db.py` is to prefer `settings.pg_password` before falling back to environment-driven token acquisition.

Update the root launcher only after both runtimes exist:

```python
# main.py
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    frontend = subprocess.Popen(["npm", "run", "dev"], cwd=ROOT / "frontend")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload"],
        cwd=ROOT,
    )
    try:
        backend.wait()
    finally:
        for proc in (frontend, backend):
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM if os.name != "nt" else signal.CTRL_BREAK_EVENT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the full verification suite**

Run:

```bash
pytest backend/tests -q
npm --prefix frontend run build
python main.py
```

Expected:

```text
all tests passed
built in
Uvicorn running on http://127.0.0.1:8000
```

- [ ] **Step 5: Commit**

```bash
git add backend frontend main.py README.md
git commit -m "feat: integrate product backend and frontend"
```

## Final Verification Checklist

- [ ] `src/` no longer contains active Python application modules
- [ ] `backend/` contains the moved route engines and new FastAPI layers
- [ ] `frontend/` builds successfully
- [ ] `/system/health` responds with `200`
- [ ] `/query/ask` routes through the orchestrator
- [ ] `/graph/answer/{query_id}` and `/graph/explorer` exist
- [ ] `/admin/overview` is admin-gated
- [ ] legacy `run_*.py` wrappers are removed
- [ ] root `main.py` launches the consolidated dev experience

## Notes for Execution

- Do the moves first, before adding large new API layers. Otherwise imports will be rewritten twice.
- Keep all legacy business logic inside the moved route packages unless a change is required for tenant-aware settings injection.
- Replace CLI tests with API tests as soon as the FastAPI surface exists.
- Do not flatten the route modules into `backend/main.py`. Consolidation is at the app surface, not by destroying module boundaries.
