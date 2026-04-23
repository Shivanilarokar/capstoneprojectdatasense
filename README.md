# SupplyChainNexus Competition Build

SupplyChainNexus is a competition-focused supply-chain intelligence system with five judge-facing routes:

- `pageindex`: SEC 10-K evidence and disclosure retrieval
- `sanctions`: deterministic OFAC/BIS screening with alias-aware matching
- `nlsql`: exact analytics over PostgreSQL source tables
- `graphrag`: graph-native dependency, hazard, and cascade reasoning
- `fullstack`: multi-route orchestration for cross-source benchmark questions

## Central Config

Runtime configuration is centralized in `config.py` and loaded from `.env`.

Key settings:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GRAPH_TENANT_ID`
- `PGHOST`
- `PGUSER`
- `PGDATABASE`
- `PGPORT`
- `PGSSLMODE`
- `PGPASSWORD` or Azure credential access for PostgreSQL
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`

## Competition Entrypoints

Primary orchestrator:

- `run_agentic_router.py`
  - LangGraph state machine with LangChain tool wrappers for `pageindex`, `sanctions`, `nlsql`, `graphrag`, and `ingestion`
  - smart OpenAI-backed routing across `pageindex`, `sanctions`, `nlsql`, `graphrag`, and `fullstack`
  - returns one answer plus route-level provenance, freshness, warnings, and raw route outputs

Examples:

```powershell
.\.venv\Scripts\python.exe .\run_agentic_router.py --question "Which states had the highest storm damage?"
.\.venv\Scripts\python.exe .\run_agentic_router.py --question "Is Acme Global sanctioned?" --force-pipeline sanctions
.\.venv\Scripts\python.exe .\run_agentic_router.py --question "Which sanctioned entities also appear in FDA warning letters?" --force-pipeline fullstack
```

Direct route launchers:

- `run_pageindex_pipeline.py`
- `run_sanctions_query.py`
- `run_nlsql_query.py`
- `run_graphrag_query.py`
- `run_graphrag_pipeline.py`

Benchmark runner:

- `run_competition_benchmark.py`

## Data Loading

Structured local datasets load into PostgreSQL through `ingestion`.

Example:

```powershell
.\.venv\Scripts\python.exe .\run_ingestion.py --source all --tenant-id default --init-schema
```

Loaded source tables:

- `source_ofac_bis_entities`
- `source_noaa_storm_events`
- `source_fda_warning_letters`
- `source_comtrade_flows`

## Benchmarking

The competition build includes a 30-query benchmark catalog in `src/evaluation/benchmarks.py`.

Example:

```powershell
.\.venv\Scripts\python.exe .\run_competition_benchmark.py --limit 5
```

Scored metrics include:

- `route_accuracy`
- `provenance_coverage`
- `freshness_disclosure_rate`
- `cross_source_completion_rate`
- `sanctions_decision_explainability`
- `cascading_risk_answer_success`
- `entity_match_precision`
- `graph_traversal_completeness`
- `geographic_accuracy`

## Current Scope

Implemented and runnable now:

- PostgreSQL ingestion for OFAC/BIS, NOAA, FDA, and Comtrade
- Neo4j graph sync pipeline from PostgreSQL + SEC sections into GraphRAG state
- standalone `pageindex`, `sanctions`, `nlsql`, and `graphrag` routes
- competition `fullstack` orchestration with checkpoint journaling, authz guard, parallel route execution, evidence validation, risk scoring, and compliance guard
- benchmark runner, richer scoring, and ablation-style summary
- structured observability artifacts under `data/observability`

Future scope after the competition:

- full frontend product surface
- RBAC and full auth
- deployment and observability polish
- broader enterprise workflow integration
