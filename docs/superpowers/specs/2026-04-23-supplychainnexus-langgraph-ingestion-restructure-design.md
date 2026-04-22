# SupplyChainNexus LangGraph Orchestration And Ingestion Restructure Design

Date: 2026-04-23

## Goal

Refactor SupplyChainNexus into a cleaner, more production-grade competition system where:

- `LangGraph` is the only orchestration runtime
- each route pipeline is exposed as a `LangChain` tool
- single-route requests stay efficient and deterministic
- `fullstack` requests use bounded multi-step agentic orchestration
- ingestion code lives in a real `src/ingestion` package
- raw datasets move out of `src` into `data/ingestion/...`

## Why This Change

The current repo has improved route coverage, but the orchestration layer is still a custom Python dispatcher instead of a true `LangGraph` workflow. It also keeps ingestion code in `src/ingestion_sql` while raw data remains inside `src/Ingestion`, which mixes code and data and makes the package layout less production-ready.

The desired target is:

- intelligent LLM-based routing
- explicit graph state and transitions
- route tools with typed input/output contracts
- deterministic boundaries for safety-critical logic
- clean separation between code and raw datasets

## Current State

### Working Strengths

- `pageindex` exists and can answer SEC filing questions
- `sanctions` exists as a deterministic screening path
- `nlsql` exists with validation and repair behavior
- `graphrag` exists with route-aware graph retrieval
- `fullstack` exists conceptually, but not yet as a real `LangGraph` workflow

### Current Weaknesses

- orchestrator is a plain Python router, not a `LangGraph`-native workflow
- route calls are direct function dispatches, not tools under graph control
- `fullstack` is a branch, not a bounded multi-step graph
- `src/ingestion_sql` and `src/Ingestion` split code and raw assets awkwardly
- raw datasets under `src` make packaging, imports, and architecture noisier

## Design Drivers

- maximize competition reliability, not agent theatrics
- preserve exactness for SQL, sanctions, and ingestion
- use `LangGraph` where it fits best: orchestration, state, routing, bounded execution
- use `LangChain` where it fits best: model wrappers, tools, structured tool interfaces
- move raw files out of the import tree
- keep the architecture easy to benchmark and explain

## Recommended Architecture

### Package Layout

#### Code Packages

- `src/ingestion`
- `src/pageindex`
- `src/sanctions`
- `src/nlsql`
- `src/graphrag`
- `src/orchestrator`
- `src/evaluation`

#### Data Layout

- `data/ingestion/ofac_bis/...`
- `data/ingestion/noaa/...`
- `data/ingestion/fda/...`
- `data/ingestion/comtrade/...`
- `data/ingestion/sec/...`

### Package Responsibilities

#### `src/ingestion`

- structured-source ingestion code only
- source specification registry
- loader entrypoints for OFAC/BIS, NOAA, FDA, Comtrade
- schema initialization and PostgreSQL load helpers
- optional ingestion tools for admin workflows

#### `src/pageindex`

- SEC extraction/indexing/runtime query code
- filing evidence retrieval
- SEC-specific route tool

#### `src/sanctions`

- deterministic name normalization and alias matching
- OFAC/BIS route query logic
- sanctions route tool

#### `src/nlsql`

- schema introspection
- structured SQL generation
- validation and repair
- safe execution
- NL-SQL route tool

#### `src/graphrag`

- graph route planning hints
- graph retrieval
- cascade/dependency reasoning
- GraphRAG route tool

#### `src/orchestrator`

- typed graph state
- route decision schema
- LangChain tool wrappers
- top-level `LangGraph` workflow
- `fullstack` subgraph
- final synthesis and normalized output

## LangGraph-Only Orchestration Model

The orchestrator should be fully rebuilt around `LangGraph`.

### Top-Level Graph

Recommended nodes:

1. `preflight`
2. `route_question`
3. conditional edge to:
   - `run_single_route`
   - `fullstack_subgraph`
4. `final_synthesis`
5. `finalize_response`

### Fullstack Subgraph

Recommended nodes:

1. `plan_fullstack`
2. `execute_next_tool`
3. conditional loop:
   - continue while more tools are needed and budget remains
   - stop when evidence is sufficient or limits are reached
4. `merge_fullstack_results`
5. return to top-level `final_synthesis`

### Why This Graph Shape

- matches current `LangGraph` guidance for structured routing and conditional edges
- keeps single-route requests cheap
- allows bounded multi-step orchestration only for `fullstack`
- makes route choice, tool calls, and fallbacks explicit in graph state

## Graph State Contract

The orchestrator state should be explicit and typed.

Minimum fields:

- `question`
- `messages`
- `route_decision`
- `planned_routes`
- `completed_routes`
- `route_results`
- `warnings`
- `provenance`
- `freshness`
- `final_answer`
- `debug`
- `error`

### State Semantics

- `route_decision`: structured router output
- `planned_routes`: ordered list of route/tool names to execute
- `completed_routes`: routes that actually ran
- `route_results`: normalized results by route
- `warnings`: aggregated route warnings and orchestration caveats
- `provenance`: route-level references assembled for the final answer
- `freshness`: route-level recency notes
- `debug`: graph-execution details useful for benchmarking and inspection

## Intelligent Router Design

The router must use OpenAI structured output, not free-form text parsing.

### Router Output Schema

- `mode`: `pageindex | sanctions | nlsql | graphrag | fullstack`
- `routes`: ordered list of route names
- `reason`: short explanation
- `confidence`: float
- `graph_routes`: optional GraphRAG route hints such as `sanctions`, `trade`, `hazard`, `cascade`

### Router Rules

- router decides what should execute next
- router never performs business logic itself
- invalid or contradictory structured output falls back to deterministic heuristics
- structured output should be used in both:
  - top-level route selection
  - optional `fullstack` planning

## LangChain Tool Model

Each route should be wrapped as a LangChain tool with typed inputs and deterministic internals.

### `pageindex_tool`

Input:

- `question`
- optional `ticker_hint`
- optional retrieval limits

Output:

- normalized result envelope with SEC evidence and provenance

### `sanctions_tool`

Input:

- `question`
- optional explicit `entity_names`

Output:

- normalized result envelope with matches, unmatched entities, and audit metadata

### `nlsql_tool`

Input:

- `question`

Output:

- normalized result envelope with SQL provenance, rows, repair info, and warnings

### `graphrag_tool`

Input:

- `question`
- optional `graph_routes_hint`

Output:

- normalized result envelope with graph evidence and graph-route provenance

### `ingestion_tool`

Input:

- `source`
- `tenant_id`
- `init_schema`
- `batch_size`

Output:

- ingestion summary

### Tooling Policy

- route tools are first-class and production-facing
- `ingestion_tool` exists for operational/admin flows
- normal end-user QA should not call `ingestion_tool`
- route tools should be composable inside `fullstack`

## Single-Route And Fullstack Execution Policy

### Single-Route

- one route chosen
- exactly one route tool executed
- final synthesis formats the result without multi-tool planning

### Fullstack

- router selects `fullstack`
- planner chooses ordered subset of route tools
- expected default order:
  - `sanctions`
  - `nlsql`
  - `graphrag`
  - `pageindex`
- graph executes only what the question needs
- final synthesis merges evidence from completed route tools

## Production-Grade Rules

### Route Efficiency

Prefer the cheapest correct route:

- `sanctions` for pure screening
- `nlsql` for exact analytics and rankings
- `graphrag` for graph-native path/cascade reasoning
- `pageindex` for SEC disclosure questions
- `fullstack` only when multiple evidence modes are clearly required

### Bounded Tool Budgets

Recommended defaults:

- max tool calls per request: `4`
- no repeated route invocation unless explicitly authorized by a repair/fallback node
- no open-ended loops
- no recursive replanning

### Deterministic Safety Boundaries

These remain deterministic:

- SQL validation and tenant enforcement
- sanctions matching and alias logic
- ingestion path resolution and DB writes
- graph query execution
- provenance assembly
- freshness assembly

These may be LLM-driven:

- route selection
- `fullstack` planning order
- final synthesis wording

### Failure Handling

Each route result should expose:

- `status`
- `route`
- `answer`
- `warnings`
- `error` if present
- `provenance`
- `freshness`

Policy:

- single-route mode returns a clear route failure
- fullstack mode allows partial success
- final synthesis must disclose missing route evidence explicitly

### Retry Policy

Allowed retries:

- one router fallback from structured output to heuristics
- one NL-SQL repair retry for validation or execution failure
- at most one retry for clearly transient tool invocation failures

Disallowed:

- repeated replanning until something works
- infinite tool retries
- route hopping to fabricate confidence

### Observability

Per request, the graph should preserve:

- chosen route
- tool call order
- route outputs
- provenance
- freshness
- warnings
- fallback usage
- router reason

This is required for:

- benchmarking
- debugging
- competition transparency

## Shared Result Envelope

All routes and the orchestrator should preserve the current normalized envelope model, with minor adjustments if needed:

- `question`
- `route`
- `answer`
- `evidence`
- `provenance`
- `freshness`
- `warnings`
- `debug`
- `status` when applicable

The orchestrator should add:

- `selected_pipeline`
- `planned_routes`
- `completed_routes`
- `route_results`

## Ingestion Restructure

### Required Move

- move raw datasets out of `src/Ingestion`
- move `src/ingestion_sql` code into `src/ingestion`

### Target Import Model

Use:

- `from ingestion.cli import ...`
- `from ingestion.load_noaa import ...`

Not:

- imports from `ingestion_sql`
- path resolution under `src/Ingestion`

### Data Path Model

Source specs should resolve under `data/ingestion/...`, not `src/...`.

This avoids:

- code/data mixing
- awkward packaging
- Windows case/path confusion around `Ingestion` vs `ingestion`

## Testing And Benchmark Expectations

### Route Tests

Keep or expand focused tests for:

- `nlsql`
- `sanctions`
- `ingestion`
- `orchestrator`
- `evaluation`

### New Orchestrator Tests

Need coverage for:

- structured route decision handling
- heuristic fallback on invalid router output
- single-route execution path
- `fullstack` planning and bounded execution
- partial route failure behavior
- final synthesis with provenance and warnings

### Benchmark Expectations

The benchmark runner should continue to score:

- `route_accuracy`
- `provenance_coverage`
- `freshness_disclosure_rate`
- `cross_source_completion_rate`
- `sanctions_decision_explainability`
- `cascading_risk_answer_success`

## What Production Grade Means For This Repo

For this competition build, production-grade means:

- `LangGraph` is the only orchestration runtime
- route pipelines are tools with typed contracts
- deterministic internals remain where exactness matters
- `fullstack` is bounded, not free-form
- code and data are cleanly separated
- route decisions and fallbacks are inspectable
- benchmark behavior is stable and defensible

It does not require:

- full enterprise deployment polish
- dashboards
- RBAC
- notification pipelines

## Recommended Implementation Direction

Implement this as:

1. move raw files to `data/ingestion`
2. rename and consolidate `ingestion_sql` into `src/ingestion`
3. add LangChain tool wrappers for each route
4. replace the current orchestrator with a `LangGraph` `StateGraph`
5. make `single-route` execution direct and efficient
6. make only `fullstack` multi-step and agentic
7. preserve deterministic safety for SQL, sanctions, graph queries, and ingestion

## Success Criteria

This redesign succeeds when:

- raw data no longer lives under `src`
- ingestion code lives under `src/ingestion`
- route pipelines are callable as tools
- top-level routing is done by `LangGraph`
- `fullstack` is a true bounded subgraph
- answers keep provenance, freshness, and warnings
- benchmarks and route tests remain stable

