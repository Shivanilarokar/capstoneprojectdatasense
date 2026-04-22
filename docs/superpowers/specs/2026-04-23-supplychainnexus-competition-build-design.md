# SupplyChainNexus Competition Build Design

Date: 2026-04-23

## Goal

Converge the current SupplyChainNexus repository into a robust, clean, competition-oriented system that maximizes benchmark performance, demo clarity, provenance quality, and rubric-aligned evidence across five judge-facing routes:

- `pageindex`
- `sanctions`
- `nlsql`
- `graphrag`
- `fullstack`

The competition build is not a full enterprise platform. It is a focused intelligence system that proves multi-source supply-chain reasoning under the capstone evaluation model.

## Effective Rubric Assumption

The repository does not currently include a separate official judging sheet. For this build, the effective rubric is derived from the existing capstone architecture and execution documents already in the repo, especially:

- `SUPPLYCHAINNEXUS_ARCHITECTURE_E2E.md`
- `TEAM_EXECUTION_PLAN_APR18.md`
- `docs/superpowers/specs/2026-04-21-supplychainnexus-nlsql-platform-design.md`

The design therefore optimizes for:

- route specialization and correctness
- graph-native multi-tier reasoning
- exact compliance/sanctions screening
- structured analytics over PostgreSQL
- SEC filing evidence retrieval
- agentic multi-route orchestration
- benchmark and evaluation evidence for 30 rubric-aligned queries

## Design Drivers

- Judges reward coherent capability more than breadth with unfinished subsystems.
- The current repo already contains the right technical spine, but it is fragmented.
- The strongest scoring path is to make the route system correct, benchmarked, and demoable.
- Platform extras such as dashboards, alerts, and deployment polish are lower leverage unless they directly improve evaluation or demo quality.

## Competition Build Scope

### In Scope

- clean, stable CLI-first runtime for all core routes
- explicit standalone route packages for:
  - `pageindex`
  - `sanctions`
  - `nlsql`
  - `graphrag`
- one orchestrated `fullstack` route for cross-source questions
- shared output envelope across all routes
- repeatable local-source ingestion into PostgreSQL
- benchmark runner for 30 rubric-aligned evaluation queries
- route-level provenance and freshness disclosure
- one clean demo flow with a shortlist of strongest showcase questions
- repo cleanup so the active implementation story matches what actually runs

### Out of Scope

- full production frontend
- complete RBAC/auth implementation
- full Azure deployment polish
- observability dashboards and alert fan-out
- notifications/webhooks
- broad enterprise platform work that does not materially improve benchmark pass rate or judge confidence

## Architecture Summary

The competition build uses a strict five-route model with one shared result contract.

### Routes

#### `pageindex`

Purpose:

- SEC 10-K evidence retrieval
- filing section reasoning
- supplier-risk disclosure extraction
- narrative support for cross-source answers

When used:

- filing-centric questions
- disclosure comparison questions
- risk-factor or management-discussion questions

#### `sanctions`

Purpose:

- deterministic entity screening
- alias-aware compliance matching
- explicit compliance rationale
- audit-friendly sanctions decision output

When used:

- sanctions screening questions
- alias/entity match questions
- compliance reasoning that must not rely on graph retrieval alone

#### `nlsql`

Purpose:

- exact analytics over PostgreSQL source tables
- grouped counts, rankings, comparisons, and trend questions
- quantitative grounding for final answers

When used:

- trade, NOAA, FDA, and sanctions-table analytics
- top-k, count, aggregate, and trend questions
- structured evidence questions

#### `graphrag`

Purpose:

- multi-tier dependency reasoning
- downstream impact and cascade analysis
- path-based supply-chain explanations
- graph-native evidence retrieval across trade, hazard, regulatory, sanctions, and financial graph routes

When used:

- tier-2/tier-3/tier-4 dependency questions
- cascade and single-point-of-failure questions
- graph-native exposure reasoning

#### `fullstack`

Purpose:

- orchestrate the other routes
- combine deterministic, structured, graph, and filing evidence
- produce one final answer with route-level provenance and warnings

When used:

- Tier 3 and Tier 4 benchmark questions
- multi-source questions that need more than one evidence mode
- demo showcase queries

## Shared Result Contract

Every route must return a normalized envelope:

- `question`
- `route`
- `answer`
- `evidence`
- `provenance`
- `freshness`
- `warnings`
- `debug`

### Envelope Semantics

- `answer`: user-facing answer text
- `evidence`: route-native structured evidence used to support the answer
- `provenance`: source references such as sections, SQL, graph routes, or matched entities
- `freshness`: source recency notes and known lag caveats
- `warnings`: missing evidence, approximation notes, or route fallbacks
- `debug`: route internals safe for benchmark inspection, not required for polished demo display

This contract is the core integration boundary for the competition build.

## Fullstack Orchestration Design

`fullstack` is the judge-facing orchestration path.

### Execution Flow

1. classify the question into one or more evidence modes
2. execute only the relevant routes
3. normalize outputs into the shared result envelope
4. fuse route evidence into one final answer
5. preserve provenance, freshness, and warnings in the final response

### Recommended Route Order

- `sanctions` first if compliance/entity screening is involved
- `nlsql` next for exact structured facts
- `graphrag` next for dependency/cascade reasoning
- `pageindex` last for filing evidence and disclosure support

### Rationale

- deterministic compliance and numeric facts should anchor the answer
- graph reasoning should build on known facts
- filing evidence should support or qualify the result, not dominate unless the question is filing-centric

## Repository Convergence Target

The repo should converge to these first-class active packages:

- `src/pageindex`
- `src/sanctions`
- `src/nlsql`
- `src/graphrag`
- `src/ingestion_sql`
- `src/orchestrator`
- `src/evaluation`

### Package Responsibilities

#### `src/pageindex`

- SEC ingestion outputs and markdown indexing
- filing retrieval and section evidence
- answer synthesis for filing-specific questions

#### `src/sanctions`

- entity normalization
- deterministic and alias-aware screening
- match explanation object
- standalone sanctions route

#### `src/nlsql`

- approved-schema SQL generation
- validation and guardrails
- safe execution against PostgreSQL
- structured numerical answer generation

#### `src/graphrag`

- route planning for graph evidence
- multi-tier topology traversal
- cross-domain graph retrieval
- cascade reasoning

#### `src/ingestion_sql`

- repeatable PostgreSQL ingestion for local structured sources
- stable paths under `src/Ingestion`
- per-source and all-source loaders

#### `src/orchestrator`

- top-level route selection
- `fullstack` orchestration
- result normalization
- final evidence fusion

#### `src/evaluation`

- 30 benchmark queries
- benchmark metadata
- runner and scorer
- saved artifacts and showcase outputs

## Data And Source Model

The competition build treats these as the active evidence layers:

- SEC 10-K evidence via `pageindex`
- OFAC/BIS entities via PostgreSQL and `sanctions`
- NOAA storm events via PostgreSQL and `nlsql`
- FDA warning letters via PostgreSQL and `nlsql`
- Comtrade trade flows via PostgreSQL and `nlsql`
- graph relationships across supplier, sanction, commodity, hazard, regulatory, and filing entities via `graphrag`

### Freshness Rules

- Comtrade lag must be explicitly disclosed
- partial or incomplete evidence must be surfaced in `warnings`
- filing and ingestion timestamps should be carried forward when available

## Benchmark And Evaluation Design

The competition build needs one explicit judging layer.

### Evaluation Package Responsibilities

`src/evaluation` must include:

- benchmark query definitions
- expected route tags
- expected evidence-mode tags
- must-mention or expected-answer constraints where useful
- runner that executes all benchmark questions
- scorer that reports route and evidence quality
- saved report artifacts for demo and submission evidence

### Recommended 30-Query Structure

- Tier 1: single-source factual retrieval
- Tier 2: exact analytics and compliance checks
- Tier 3: graph and multi-hop reasoning
- Tier 4: cross-source orchestration

### Required Scoring Signals

- `route_accuracy`
- `provenance_coverage`
- `freshness_disclosure_rate`
- `cross_source_completion_rate`
- `sanctions_decision_explainability`
- `cascading_risk_answer_success`

### Judge-Facing Outputs

The system should produce:

- benchmark summary table
- pass/fail by query
- chosen route versus expected route
- provenance presence
- freshness-caveat presence
- a small showcase set of saved high-quality outputs

## Cleanup Strategy

The competition build must remove confidence-damaging noise.

### Required Cleanup

- merge the stronger OpenAI-driven `nlsql` implementation into the active main runtime
- remove or quarantine the old heuristic-only `nlsql` path
- keep one canonical ingestion data root under `src/Ingestion`
- fix stale path references and duplicated source references
- remove placeholder or low-signal judge-facing files from the active flow
- align README and runtime docs with the actual competition build

### Documentation Policy

The README and architecture summary should clearly distinguish:

- what is implemented and runnable now
- what is future scope after the competition

This avoids overclaiming and improves judge trust.

## Demo Strategy

The demo should be benchmark-backed, not improvised.

### Demo Flow

1. show source ingestion status
2. run one strong `pageindex` query
3. run one strong `sanctions` query
4. run one strong `nlsql` analytics query
5. run one strong `graphrag` dependency/cascade query
6. run two or three `fullstack` cross-source showcase queries
7. show evaluation summary and benchmark pass evidence

### Demo Principles

- answers must carry provenance
- freshness caveats must appear where relevant
- failure modes must be explicit and clean
- outputs should look deliberate and repeatable

## Phased Implementation Priorities

### Phase 1: Competition Core

- converge route packages
- land strong `nlsql`
- add explicit `sanctions`
- normalize outputs
- upgrade orchestrator to five-route plus `fullstack`

### Phase 2: Judging Proof

- build `src/evaluation`
- add 30 benchmark queries
- add runner and scorer
- add demo script and showcase queries

### Phase 3: Hardening And Cleanup

- remove stale code and placeholder files
- align docs
- improve failure messages and caveat handling

## Definition Of Done

The competition build is done when:

- all four core evidence modes plus `fullstack` run from the repo
- ingestion is repeatable and stable
- every route emits the shared result envelope
- benchmark runner executes the 30-query suite
- outputs preserve provenance and freshness language
- the demo path is stable, clean, and defensible
- the repository tells one coherent story that matches the actual implementation

## Success Criteria

This design succeeds if judges experience the system as:

- specialized rather than bloated
- benchmarked rather than hand-waved
- evidence-backed rather than purely generative
- clean and deliberate rather than half-enterprise and half-prototype

The winning strategy is not maximum breadth. It is maximum trust, proof, and coherence.
