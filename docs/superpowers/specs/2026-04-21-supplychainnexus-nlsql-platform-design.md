## SupplyChainNexus Platform Design

Date: 2026-04-21

### Goal

Extend the current SupplyChainNexus codebase into a rubric-complete capstone platform with:

- standalone `pageindex`, `sanctions`, `nlsql`, and `graphrag` routes
- a `fullstack` LangGraph orchestration path for multi-hop cross-source questions
- repeatable PostgreSQL ingestion for all local non-EDGAR sources
- production-oriented app architecture covering auth, multi-tenancy, auditability, observability, evaluation, notifications, and deployability

### Design Drivers

- The capstone explicitly requires graph-native reasoning for multi-tier supply chain exposure.
- The capstone explicitly requires exact entity matching for sanctions/compliance.
- The capstone explicitly requires structured numerical aggregation for trade and event data.
- The capstone explicitly requires page indexing / long-document handling for SEC 10-K filings.
- The capstone explicitly rewards agentic multi-step orchestration across heterogeneous sources.

### Architecture Summary

Use `LangGraph` as the control plane and `LangChain` tools as the execution plane.

The system has five execution modes:

- `pageindex`
- `sanctions`
- `nlsql`
- `graphrag`
- `fullstack`

`fullstack` is the only multi-route orchestration mode. Pairwise hybrids are intentionally not supported.

### Route Boundaries

#### `pageindex`

Purpose:

- SEC 10-K retrieval and synthesis
- section-aware filing search
- supplier and risk disclosure extraction
- temporal filing comparison

When selected:

- filing-centric questions
- disclosure comparison questions
- questions centered on Item 1A, Item 7, Notes, supplier concentration, or filing language

#### `sanctions`

Purpose:

- deterministic sanctions/entity screening
- alias normalization and exact-match decisions
- compliance audit logging

When selected:

- OFAC/BIS/entity-list questions
- direct entity screening
- compliance-focused name matching

#### `nlsql`

Purpose:

- exact SQL-based analytics over PostgreSQL source tables
- aggregations, rankings, counts, trends, date filters, country comparisons
- structured tabular evidence retrieval

When selected:

- trade, NOAA, FDA, and sanctions table analytics
- top-k and percentage questions
- temporal trend questions
- grouped summaries and filtered list questions

#### `graphrag`

Purpose:

- multi-tier graph traversal
- dependency path search
- cascading risk and downstream impact reasoning
- graph-native exposure analysis

When selected:

- supplier dependency questions
- path and blast-radius questions
- Tier 2/Tier 3/Tier 4 graph-native reasoning

#### `fullstack`

Purpose:

- orchestrate across `pageindex`, `sanctions`, `nlsql`, and `graphrag`
- combine structured analytics, graph traversal, entity screening, and filing evidence
- produce one synthesized answer with provenance

When selected:

- cross-source Tier 3 and Tier 4 capstone queries
- questions requiring multiple evidence types and multi-step reasoning

### Orchestration Design

The top-level orchestrator remains in `src/orchestrator/agent.py` but is restructured around `LangGraph` `StateGraph`.

High-level flow:

1. Accept user question plus tenant and user context.
2. Run a router/planner node.
3. Choose one of `pageindex`, `sanctions`, `nlsql`, `graphrag`, or `fullstack`.
4. Execute the selected node or subgraph.
5. Collect provenance, errors, and route decisions.
6. Produce a final answer.

`fullstack` is implemented as a dedicated graph path that runs a LangChain tool-calling agent with access to domain tools.

### LangChain Tool Layer

Define explicit application tools with strong descriptions so the agent can select the right tool based on the question:

- `pageindex_search`
- `screen_sanctions`
- `run_nlsql`
- `traverse_supply_graph`
- `compute_risk_summary`
- `fetch_provenance`

The router should not expose raw internal implementation details. It selects mode; the `fullstack` path selects tools.

### Repository Structure

#### Existing packages retained

- `src/pageindex/`
- `src/graphrag/`
- `src/orchestrator/`
- `src/common/`

#### New packages

- `src/nlsql/`
- `src/ingestion_sql/`
- `src/sanctions/`
- `src/webapi/` for FastAPI service layer
- `src/evaluation/` for benchmarks, RAGAS, and ablation support

### New Package Responsibilities

#### `src/nlsql/`

- `db.py`: psycopg connection management and token refresh
- `schema.py`: table metadata and exposed queryable semantics
- `planner.py`: question-to-SQL intent planning
- `executor.py`: safe SQL execution and guardrails
- `synthesizer.py`: result formatting and answer generation
- `cli.py`: direct route runner

#### `src/ingestion_sql/`

- `base.py`: shared loader helpers
- `load_ofac_bis.py`
- `load_comtrade.py`
- `load_noaa.py`
- `load_fda.py`
- `cli.py`: load one source or all sources

#### `src/sanctions/`

- `matcher.py`: alias normalization and exact-match logic
- `query.py`: standalone sanctions route
- `audit.py`: compliance audit logging

### PostgreSQL Design

PostgreSQL stores source tables first, not a unified canonical warehouse in v1.

Initial source tables:

- `source_ofac_bis_entities`
- `source_comtrade_flows`
- `source_noaa_storm_events`
- `source_fda_warning_letters`

Each table should include:

- a stable natural key or source-derived upsert key
- a `tenant_id`
- `source_file_name`
- `source_loaded_at`
- `source_updated_at` where derivable
- normalized columns required for querying
- raw payload column when useful for traceability

### Ingestion Strategy

The ingestion layer is repeatable and idempotent.

Requirements:

- load local files from `src/Ingestion`
- support per-source and all-source commands
- upsert by stable source keys
- maintain tenant isolation
- expose run summaries and failures
- be safe to re-run whenever source files change

Ingestion sources:

- `src/Ingestion/OFAC+BIS_Entity/sdn_data.xlsx`
- `src/Ingestion/Un_comtrad_International_tradedata/TradeData.xlsx`
- `src/Ingestion/NOAAA_StormEventsDetailsData/StormEvents_details-ftp_v1.0_d1950_c20260323.csv`
- `src/Ingestion/FDAWarningletters+Importalerts/warning-letters.xlsx`

EDGAR data remains outside PostgreSQL and continues through `pageindex`.

### Azure PostgreSQL Authentication

The application acquires and refreshes Azure PostgreSQL access tokens at runtime.

Auth strategy:

- local development: Azure CLI login
- deployed environment: Managed Identity
- credential acquisition: `DefaultAzureCredential`
- DB connection: psycopg using a fresh access token as password at connection time

The app should not depend on manual `PGPASSWORD` export during normal operation.

### Multi-Tenancy

Multi-tenancy is required across:

- PostgreSQL source tables
- graph queries
- audit logs
- document lifecycle metadata
- frontend-visible query history and admin views

Minimum tenant pattern:

- every query carries `tenant_id`
- every table includes `tenant_id`
- every route filters by tenant
- audit and provenance records are tenant-scoped

### Document Lifecycle

Document lifecycle applies primarily to SEC and uploaded artifacts.

Lifecycle states:

- uploaded
- parsed
- indexed
- queryable
- archived

Metadata belongs in PostgreSQL, binary content belongs in storage.

### Web Application

Frontend requirements:

- React query interface
- admin dashboard
- graph visualization view
- ingestion/status page
- evaluation/status page

Backend requirements:

- FastAPI
- role-based access
- tenant-scoped APIs
- route invocation endpoint
- ingestion management endpoints
- evaluation endpoints
- graph visualization data endpoint

### Knowledge Graph View

The app needs a supply chain graph visualization backed by Neo4j traversal results.

The visualization should show:

- company
- supplier
- facility
- component
- raw material
- country
- hazard exposure
- sanctions status

### Entity Resolution

Sanctions matching must be explicit and measurable.

Requirements:

- normalization rules
- alias handling
- exact and near-exact explainability
- logged match decisions
- auditable reasons for match/non-match

### Observability and Logging

Use structured JSON logs with correlation IDs end to end.

Required tracing domains:

- router decisions
- tool calls
- SQL generation and execution
- graph traversal
- sanctions matching
- pageindex retrieval
- final synthesis

Preferred observability integration:

- LangSmith

Optional parallel support later:

- LangFuse

### Notifications

Support Slack/webhook notifications for:

- ingestion success/failure
- evaluation completion
- sanctions/risk alert conditions
- monitored entity updates

### Evaluation

Evaluation package must cover:

- rubric-aligned benchmark query set
- RAGAS-based answer quality evaluation where applicable
- custom `cascading_risk_score`
- entity match precision/recall
- route selection accuracy
- ablation comparisons by component

### Ablation Study

Ablation dimensions:

- without `pageindex`
- without `sanctions`
- without `nlsql`
- without `graphrag`
- without `fullstack`

Measure impact on:

- answer completeness
- factual grounding
- route success on benchmark tiers
- cascading-risk accuracy

### Security and RBAC

Roles at minimum:

- analyst
- admin

Analyst:

- run queries
- view allowed tenant data

Admin:

- manage ingestion
- review audit logs
- view evaluation and system health

### Deployment Target

Production target stack:

- React frontend
- FastAPI backend
- PostgreSQL
- Neo4j
- Azure deployment

The architecture should support a live deployed URL and a demo walkthrough.

### Phased Build Plan

#### Phase 1: Data and SQL foundation

- PostgreSQL token-auth layer
- source table DDL
- repeatable ingestion commands
- direct `nlsql` route

#### Phase 2: Router refactor

- add `sanctions`, `nlsql`, and `fullstack`
- convert orchestrator to LangGraph-native routing flow
- add LangChain tools for domain actions

#### Phase 3: Domain quality

- sanctions entity resolution route
- graph route cleanup
- provenance and audit trail
- benchmark-ready output structure

#### Phase 4: Product layer

- FastAPI
- React UI
- admin dashboard
- graph view

#### Phase 5: Evaluation and operations

- RAGAS
- cascading risk metric
- ablations
- LangSmith
- Slack/webhooks
- demo/documentation

### Out of Scope for Initial Implementation Slice

- pairwise hybrid orchestration
- full canonical warehouse model across all sources
- exhaustive frontend polish before backend route correctness

### Success Criteria

The implementation is successful when:

- all four retrieval strategies exist as distinct routes
- `fullstack` orchestrates across them when required
- local non-EDGAR sources can be reloaded into PostgreSQL with upsert logic
- sanctions matching is auditable
- graph traversal remains graph-native
- SQL analytics remain SQL-native
- the platform is structured for deployment, evaluation, and demo

