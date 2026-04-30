# SupplyChainNexus Product Consolidation Design

**Date:** 2026-04-27

**Status:** Draft for review

**Owner:** Codex

## Goal

Transform the current competition-style, CLI-driven SupplyChainNexus codebase into a product-style platform with:

- one consolidated FastAPI backend entrypoint
- no user-facing CLI surface
- preserved internal route modules for `pageindex`, `sanctions`, `nlsql`, `graphrag`, and `orchestrator`
- a Vite + React + TypeScript frontend
- Microsoft Entra External ID authentication with Google and Microsoft social login only
- role-based access control for `user` and `admin`
- automatic customer signup with automatic tenant provisioning
- hard per-tenant database isolation using a dedicated Postgres database and Neo4j database per tenant
- a query-first UI backed only by the top-level orchestrator
- a knowledge graph experience with both query-scoped and global exploration views

## Why This Change

The current repository is optimized for route isolation, local testing, and competition benchmarking. It exposes many top-level runner scripts and per-route CLIs that are useful for development but do not form a coherent product surface.

The new target state is a single deployable application platform with:

- one backend app runtime
- one frontend app runtime
- one user-facing query experience
- one admin dashboard
- one graph experience

Internal modularity is preserved. Public fragmentation is removed.

## Non-Goals

This phase does not attempt to:

- merge all backend logic into one file
- rewrite the core route engines from scratch
- expose route-specific query selection to normal users
- provide write-capable admin actions in v1
- provide local username/password authentication
- implement a fully separate app deployment per tenant

## Product Requirements

### User Experience

- External users access the product through a React SPA.
- Authentication is handled by Microsoft Entra External ID.
- Supported sign-in providers are Google and Microsoft only.
- Normal users use a single top-level query interface that always hits the orchestrator.
- Users can inspect answer provenance, warnings, freshness notes, and evidence.
- Users can move from an answer into a graph view for that answer.
- Users can also browse a broader graph explorer.

### Admin Experience

- Admin users can access a read-only dashboard.
- Admin users can view tenant summaries, health summaries, query activity, and graph statistics.
- Admin users cannot trigger ingestion, GraphRAG sync, benchmark execution, or any operational jobs from the UI in v1.

### Roles

- `user`
  - access query workspace
  - access answer-scoped graph
  - access global graph explorer
- `admin`
  - everything a user can access
  - access read-only admin dashboard

## High-Level Architecture

The system will be restructured into three product layers:

1. **FastAPI application layer**
   - single public backend entrypoint
   - API routers for auth, tenant lifecycle, query, graph, admin, and system endpoints

2. **Internal service layer**
   - preserves the current route modules:
     - `pageindex`
     - `sanctions`
     - `nlsql`
     - `graphrag`
     - `orchestrator`
   - adds thin service adapters instead of route rewrites

3. **React frontend layer**
   - SPA built with Vite + React + TypeScript
   - route-gated app shell with query, graph, and admin areas

## Migration Strategy

The recommended strategy is a strangler migration over the existing route modules.

### Why

- preserves working route logic
- reduces regression risk
- shortens time to delivery
- allows the backend API surface to stabilize before full frontend integration

### What Changes

- top-level `run_*.py` scripts stop being the primary product surface
- per-route CLIs become optional internal/dev utilities or are retired
- the FastAPI app becomes the only public backend entrypoint
- the React SPA becomes the only public frontend entrypoint

## Backend Design

### Backend Runtime

The backend will expose one application entrypoint, for example:

```bash
uvicorn app.main:app --reload
```

The backend must not require users to invoke route-specific CLIs.

### Internal Layering

The backend should be decomposed into:

- `app/main.py`
  - FastAPI app construction
  - middleware
  - router registration
- `app/api/`
  - HTTP routers and request/response models
- `app/auth/`
  - Entra External ID token validation
  - role extraction
  - auth dependencies
- `app/tenancy/`
  - tenant resolution
  - tenant provisioning
  - tenant connection registry
- `app/services/`
  - adapters over existing route modules
- `app/control_plane/`
  - shared metadata persistence and provisioning workflows
- `app/graph/`
  - graph response shaping for UI consumption

The existing `src/*` route packages remain intact and are called from service adapters.

## Control Plane vs Query Plane

The backend must separate platform control concerns from business query concerns.

### Control Plane

Responsibilities:

- tenant signup intake
- tenant status tracking
- Entra identity mapping
- per-tenant connection metadata
- provisioning orchestration
- audit metadata

### Query Plane

Responsibilities:

- top-level orchestrator queries
- graph data retrieval
- admin read-only reporting
- answer history and evidence access

## Tenant Isolation Model

### Hard Isolation Requirement

Each customer tenant gets:

- a dedicated Postgres database
- a dedicated Neo4j database

The application deployment is shared, but data stores are not.

### Shared Metadata Store

The platform also needs one small shared control-plane database to hold:

- tenant records
- tenant lifecycle state
- user-to-tenant identity mappings
- connection metadata for each tenant's dedicated Postgres and Neo4j databases
- query/session audit metadata
- provisioning audit metadata

This shared metadata store must never hold the tenant's business data that belongs in route-specific storage.

### Tenant Resolution

Tenant identity must not come from free-form user input.

Per request, the backend must:

1. validate the bearer token
2. identify the signed-in user
3. resolve the user's tenant through trusted identity mapping
4. load the tenant's Postgres and Neo4j connection info
5. build a tenant-scoped service context
6. execute the requested operation only against that tenant's databases

## Identity and Access Management

### Authentication

Use Microsoft Entra External ID for public-facing external users.

Supported identity providers:

- Google
- Microsoft

Unsupported in v1:

- local email/password
- open anonymous access
- route-level bypass auth

### Authorization

The API will enforce authorization using app roles carried in token claims.

Expected roles:

- `user`
- `admin`

The backend must read roles from the validated token and enforce them through dependencies on routers and endpoints.

### Session Model

The React SPA authenticates the user and receives tokens through the Entra External ID flow. The FastAPI API validates bearer tokens on each protected request.

The frontend may maintain session bootstrap state, but the API remains the source of truth for access checks.

## Automatic Tenant Provisioning

Tenant signup must support customer onboarding with automatic provisioning.

### Provisioning Flow

1. User signs up through Entra External ID.
2. Platform receives onboarding context.
3. A new tenant record is created in the control-plane store.
4. A dedicated Postgres database is provisioned for that tenant.
5. A dedicated Neo4j database is provisioned for that tenant.
6. Tenant connection metadata is stored.
7. The tenant transitions to `active` only after all provisioning steps succeed.

### Tenant States

- `provisioning`
- `active`
- `failed`
- `suspended`

### Failure Semantics

- provisioning must be atomic from the product's perspective
- partially provisioned tenants must never appear active
- failed tenants remain visible to admins with failure details

## API Surface

The product should expose API routers rather than CLI commands.

### `/auth/*`

Responsibilities:

- authenticated session bootstrap
- current user profile
- effective role discovery
- tenant summary for the signed-in user

### `/tenants/*`

Responsibilities:

- signup callback completion
- provisioning status
- tenant metadata lookup for authorized actors

### `/query/*`

Responsibilities:

- one top-level orchestrator-backed query endpoint
- query history
- single query detail
- answer evidence and provenance access

### `/graph/*`

Responsibilities:

- answer-scoped subgraph for a specific query result
- global graph explorer
- graph search and filtered graph retrieval
- node and edge detail retrieval for UI panels

### `/admin/*`

Responsibilities:

- read-only tenant summaries
- read-only user summaries
- route success/failure metrics
- query volume/activity summaries
- database connectivity and health summaries
- graph summary statistics

### `/system/*`

Responsibilities:

- health checks
- readiness checks
- build/version metadata

## Query Execution Model

Normal users interact with only one product-level query action:

- `Ask SupplyChainNexus`

This action always calls the top-level orchestrator.

### User-Facing Query Constraints

- no route picker in the UI
- no route forcing in the UI
- no direct access to `pageindex`, `sanctions`, `nlsql`, or `graphrag` from the normal user workflow

### Internal Execution Model

The orchestrator remains responsible for:

- selecting the route plan
- invoking individual routes
- parallel route execution where required
- evidence validation
- risk scoring
- compliance output guard behavior
- final answer assembly

## Graph Experience

The product must support two graph modes.

### 1. Query-Scoped Answer Graph

Purpose:

- display the graph structures directly relevant to the current answer

Behavior:

- derived from orchestrator and GraphRAG evidence
- highlights companies, suppliers, sanctions, hazards, trade nodes, materials, and path edges relevant to the answer
- links graph nodes back to the answer evidence where possible

### 2. Global Graph Explorer

Purpose:

- allow broader exploration of the tenant's graph data

Behavior:

- graph search
- node-type filters
- relationship-type filters
- drill-down details
- neighborhood expansion
- pagination or bounded expansion for large traversals

### Graph Rendering

Use Cytoscape.js in the React app for graph visualization because the product needs:

- relational graph rendering
- interactive node and edge selection
- path highlighting
- filtering
- incremental exploration

## Frontend Design

### Frontend Runtime

The frontend will be a separate Vite + React + TypeScript SPA.

Public runtime entrypoint:

```bash
npm run dev
```

### App Structure

The SPA should provide three main areas:

- `Query`
- `Graph`
- `Admin`

### Route Gating

- users with `user` role:
  - query workspace
  - answer graph
  - graph explorer
- users with `admin` role:
  - all user capabilities
  - read-only admin dashboard

### Visual Direction

The UI should avoid a generic commodity dashboard look.

Recommended visual direction:

- warm off-white base
- steel/ink neutrals
- restrained risk-state colors
- typography with analytical density
- subtle topology and map-inspired motifs
- emphasis on evidence and relationships, not just tables

### Core Screens

#### Landing / Sign-In

- Microsoft Entra External ID sign-in
- Google and Microsoft social options
- clear product positioning

#### Query Workspace

- one prominent query input
- answer area
- provenance/evidence modules
- warnings and freshness disclosures
- graph handoff into answer-scoped graph view

#### Graph View

Two tabs or equivalent sections:

- `Answer Graph`
- `Explorer`

#### Admin Dashboard

Read-only analytical views for:

- tenant summaries
- user summaries
- system health
- query metrics
- graph metrics

## Frontend State Management

State must be separated by concern.

### Auth State

- identity/session bootstrap
- role awareness
- current tenant context

### Query State

- current prompt
- answer payload
- evidence sections
- answer history

### Graph State

- active graph mode
- selected nodes/edges
- filters
- neighborhood expansion state

Ad hoc local state for everything is not acceptable. The frontend should use structured API-backed state management suitable for caching and invalidation.

## Backend-to-Frontend Contracts

The backend must return models designed for the product, not raw internal route payloads.

### Query Response Requirements

The top-level query response should support:

- answer text
- selected pipeline
- route plan
- route results summary
- provenance
- freshness
- warnings
- evidence sections
- graph handoff metadata
- query id

### Graph Response Requirements

Graph endpoints should return UI-oriented graph JSON including:

- nodes
- edges
- categories/types
- styles or semantic node classes
- path emphasis metadata
- expandable references where needed

### Admin Response Requirements

Admin endpoints should return stable summary shapes for:

- cards
- tables
- trend charts
- health indicators

## Error Handling

### Authentication and Authorization

- invalid or missing token returns `401`
- insufficient role returns `403`
- frontend shows clear role-aware messaging

### Provisioning

- provisioning errors leave the tenant in `failed`
- failed provisioning never produces an active tenant
- error details are visible to admins, not to regular users

### Querying

- route failures should degrade gracefully where partial results are still meaningful
- orchestrator responses should expose warnings and partial evidence instead of collapsing the whole UX where possible

### Tenant Connectivity

- Postgres or Neo4j failures for one tenant must remain isolated to that tenant
- admin dashboard should expose tenant-level health visibility

### Graph Rendering

- graph endpoint failures should degrade to structured evidence/detail panels instead of blank pages

## Security Requirements

- no free-form tenant selection in the UI for normal product access
- no cross-tenant connection fallback
- no user-facing direct CLI surface
- all protected endpoints validate bearer tokens
- all privileged admin endpoints require `admin`
- query and graph responses must only use the resolved tenant's dedicated databases

## Testing Strategy

### Backend Unit Tests

- auth token validation helpers
- role enforcement dependencies
- tenant resolution
- tenant connection registry
- response serializers/adapters

### Backend Integration Tests

- orchestrator-backed `/query` endpoint
- `/graph` answer-graph endpoint
- `/graph` explorer endpoint
- `/admin` read-only metrics endpoints
- `/system` readiness behavior

### Tenant Isolation Tests

Must explicitly prove:

- one tenant cannot resolve another tenant's Postgres database
- one tenant cannot resolve another tenant's Neo4j database
- cross-tenant query leakage is blocked
- graph explorer cannot traverse another tenant's graph

### Frontend Tests

- auth bootstrap
- role-gated routes
- query submission flow
- answer rendering
- graph panel rendering
- admin dashboard rendering

### End-to-End Tests

- external sign-in
- signup and automatic tenant provisioning
- active tenant query flow
- answer-to-graph transition
- global graph explorer access
- admin dashboard access for admin role

## Delivery Plan

Implementation should proceed in these phases:

### Phase 1: Backend Consolidation

- add FastAPI app skeleton
- add router structure
- add service adapters over current route modules
- move product entrypoint to FastAPI
- remove CLI as primary product surface

### Phase 2: Auth and Tenancy

- Entra External ID integration
- token validation
- role enforcement
- control-plane metadata model
- tenant resolution and per-tenant connection management
- automatic provisioning flow

### Phase 3: Product APIs

- query endpoints
- graph endpoints
- admin endpoints
- system endpoints

### Phase 4: React App

- SPA scaffold
- auth bootstrap
- query workspace
- graph pages
- admin dashboard

### Phase 5: Graph Refinement and Hardening

- answer-scoped graph polish
- explorer filtering
- path highlighting
- performance limits
- final UX refinement

## Acceptance Criteria

The product consolidation is successful when:

- there is one backend app entrypoint
- there is one frontend app entrypoint
- normal users only use the top-level orchestrator query experience
- route modules remain internal and modular
- the app uses Entra External ID with Google and Microsoft login only
- roles `user` and `admin` are enforced
- customer signup triggers automatic tenant provisioning
- each tenant uses its own Postgres and Neo4j databases
- admin dashboard is read-only
- graph supports both answer-scoped and global exploration modes

## Implementation Risks

- automatic provisioning across two dedicated databases per tenant is a real control-plane problem and will need careful sequencing
- current route modules assume a more static config model and will need tenant-scoped connection injection
- GraphRAG and admin graph summary endpoints depend on reliable Neo4j access patterns
- the orchestrator output shape may need normalization before it is frontend-safe

## Recommendation

Proceed with a strangler migration that preserves the current route engines behind a new FastAPI app and builds the React product against stable product-oriented API contracts.
