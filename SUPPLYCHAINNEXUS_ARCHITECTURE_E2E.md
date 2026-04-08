# SupplyChainNexus End-to-End Architecture Blueprint (Win Plan)

**Project:** SupplyChainNexus: Multi-Tier Supplier Risk Intelligence  
**Industry:** Manufacturing / Procurement / Supply Chain  
**Difficulty:** Enterprise-Grade  
**Deadline:** April 18, 2026  
**Document Version:** v1.0 (prepared April 8, 2026)  
**Prepared For:** Capstone implementation using fixed stack constraints

---

## 1) Executive Summary

This document defines the full production architecture for **SupplyChainNexus** with the fixed stack:

- **Vector database:** Pinecone
- **Agentic framework:** LangGraph
- **Embeddings + LLM:** OpenAI models
- **Deployment:** Azure

The system solves deep multi-tier supply-chain risk reasoning by combining:

- hybrid semantic retrieval (Pinecone),
- graph traversal (Neo4j),
- structured analytics (PostgreSQL compute + query tools),
- deterministic sanctions entity matching,
- multi-agent orchestration (LangGraph),
- full enterprise controls (RBAC, multi-tenancy, audit trail, observability, alerts).

The architecture is designed to satisfy all capstone required concepts, all enterprise requirements, all deliverables, and all four evaluation tiers (30 benchmark queries).

---

## 2) Problem Definition and Why Naive RAG Fails

Global automotive and electronics supply chains have:

- 1,000+ to 3,000+ suppliers per product,
- 4–5 tier dependencies,
- cross-border commodity flows,
- sanctions compliance risk,
- geospatial hazard exposure,
- temporal and cross-domain cascading failures.

Why semantic search alone fails:

- alias/entity resolution (sanctions) needs deterministic matching, not only cosine similarity.
- graph traversal questions require linked reasoning across nodes and edges.
- numerical aggregation questions require structured computation.
- temporal deltas require recency-aware comparisons.
- cross-domain correlation requires joining heterogeneous datasets.

---

## 3) Fixed Technology Decisions (Non-Negotiable Stack)

## 3.1 Core Stack

- **Orchestration:** LangGraph (stateful, durable, checkpointed execution)
- **Vector Retrieval:** Pinecone (hybrid retrieval + metadata filters + tenant namespaces)
- **LLM + Embeddings:** OpenAI
- **Cloud Deployment:** Azure

## 3.2 Model Matrix (Recommended)

- **Embedding model:** `text-embedding-3-large`
  - default dimension 3072
  - supports dimensions downscaling if needed
- **Primary synthesis model:** `gpt-4.1`
  - long-context, high-fidelity report generation
- **Primary orchestration/reasoning model:** `o4-mini`
  - fast reasoning and tool control loops
- **Escalation model for hardest multi-hop reasoning:** `o3` (selective use only)

---

## 4) High-Level System Architecture

```text
React Frontend (Azure Static Web Apps)
  -> API Gateway (FastAPI on Azure Container Apps)
      -> LangGraph Orchestrator
          -> Router + Specialist Tool Agents
              - Financial Agent (SEC)
              - Sanctions Agent (OFAC/BIS)
              - Trade Agent (Comtrade)
              - Hazard Agent (NOAA)
              - Regulatory Agent (FDA)
              - Graph Agent (Neo4j traversal)
          -> Evidence Fusion
          -> Cascading Risk Scoring
          -> Response + Citations + Provenance

Data Layer:
  Blob Storage (raw/parsed artifacts)
  PostgreSQL (canonical entities, metrics, audit, evaluation)
  Neo4j (knowledge graph)
  Pinecone (vector index per env, namespace per tenant)

Event/Async Layer:
  Azure Container Apps Jobs + Azure Functions (scheduled ingestion)
  Service Bus queues (pipeline decoupling)
  Event Grid + Logic Apps (alerts/webhooks)

Ops/Security:
  Entra ID (auth), Key Vault (secrets), LangSmith + Azure Monitor
```

---

## 5) Azure Deployment Architecture

## 5.1 Azure Services

- **Azure Static Web Apps:** React frontend
- **Azure Container Apps:** FastAPI backend and background workers
- **Azure Container Apps Jobs / Azure Functions Timer Triggers:** scheduled ingestion
- **Azure Database for PostgreSQL (Flexible Server):** operational + analytics tables
- **Azure Blob Storage:** raw + parsed + archived document lifecycle
- **Azure Key Vault:** secret and key management
- **Azure Service Bus:** ingestion/event queues
- **Azure Event Grid + Logic Apps:** alert fan-out to Slack/webhooks
- **Azure Monitor + Application Insights:** logs/metrics/traces

## 5.2 Network and Security

- private endpoints where possible (DB, Storage, Key Vault)
- managed identity for service-to-service auth
- no static secrets in code
- least-privilege role assignments
- TLS everywhere

---

## 6) Data Sources and Integration Plan

## 6.1 Required 5 Core Sources

1. **SEC EDGAR 10-K Filings**
   - ingestion: scheduled + on-demand by ticker/company list
   - parse targets: Item 1A, Item 7, Notes, supplier mentions
2. **OFAC SDN + BIS Entity List**
   - ingestion: daily diff + full sync fallback
   - parse targets: names, aliases, addresses, IDs, programs
3. **UN Comtrade**
   - ingestion: periodic batch by HS code families and countries
   - parse targets: yearly trade flows, quantity/value, direction
4. **NOAA Storm Events**
   - ingestion: periodic full + incremental updates
   - parse targets: event type, geo coords, date, severity/damage
5. **FDA Warning Letters + Import Alerts**
   - ingestion: scheduled crawler/parser
   - parse targets: company, date, location, violation semantics

## 6.2 Additional Sources (Required 2+)

1. **USGS Mineral Commodity Summaries**
   - critical mineral concentration and supply dependency context
2. **World Bank Logistics Performance Index (LPI)**
   - country-level logistics resilience and bottleneck risk features

---

## 7) Canonical Data Model

## 7.1 Primary Entities

- `tenant`
- `company`
- `supplier`
- `facility`
- `component`
- `raw_material`
- `product_line`
- `country`
- `hazard_event`
- `sanctions_entity`
- `regulatory_event`
- `trade_flow`
- `filing_document`
- `entity_alias`

## 7.2 Canonical Keys

- internal UUIDs for every canonical entity
- source-specific keys preserved (`source_id`, `source_system`)
- crosswalk tables for alias and source-to-canonical mapping

## 7.3 Temporal Columns

- `effective_date`, `reported_date`, `ingested_at`, `source_snapshot_date`

---

## 8) Storage Strategy

## 8.1 Blob Storage

- `/raw/{source}/{yyyy-mm-dd}/...`
- `/parsed/{source}/{yyyy-mm-dd}/...`
- `/archive/{source}/{yyyy-mm-dd}/...`

## 8.2 PostgreSQL

- canonical entities
- scoring tables
- query/audit logs
- evaluation datasets and results
- routing outcomes
- ingestion job status

## 8.3 Pinecone

- one index per environment (`dev`, `staging`, `prod`)
- namespace per tenant
- rich metadata filters:
  - tenant, source, section, filing year/quarter, country, entity type, timestamp

## 8.4 Neo4j

- full supply graph + risk relationships
- support multi-hop traversal for dependency impact analysis

---

## 9) Knowledge Graph Design

## 9.1 Node Types

- Company
- Supplier
- Facility
- Component
- RawMaterial
- ProductLine
- Country
- HazardZone
- SanctionsStatus
- RegulatorySignal
- TradeRoute
- Filing

## 9.2 Edge Types

- `SUPPLIES`
- `SUBSUPPLIER_OF`
- `PRODUCES_COMPONENT`
- `USES_RAW_MATERIAL`
- `LOCATED_IN`
- `EXPOSED_TO_HAZARD`
- `HAS_SANCTIONS_MATCH`
- `HAS_REGULATORY_SIGNAL`
- `FLOWS_THROUGH`
- `DISCLOSED_IN`

## 9.3 Core Traversals

- upstream raw-material lineage per product
- downstream blast radius from supplier/facility failure
- alternative supplier path search
- exposure intersection traversal:
  - sanctions jurisdiction AND hazard zone AND concentration risk

---

## 10) Ingestion and Processing Pipelines

## 10.1 Pipeline Stages

1. collect raw
2. parse and normalize
3. canonicalize entities
4. extract relationships
5. index text/table chunks
6. upsert vector + graph + SQL
7. run data quality checks
8. emit status/alerts

## 10.2 SEC Book/Page Indexing Strategy

- prioritize sections:
  - Item 1A Risk Factors
  - Item 7 MD&A
  - Notes to Financial Statements
- chunking:
  - section-aware, overlapping chunks
  - table chunks handled separately from narrative chunks
- preserve:
  - filing year, quarter (if available), section path, page anchors
- extraction:
  - supplier mentions, concentration cues, single-source signals, going-concern language

## 10.3 FDA and Semi-Structured Parsing

- extract entity and location fields
- classify violation categories and severity
- map findings into standardized risk taxonomy

---

## 11) Sanctions Entity Resolution (Compliance-Critical)

## 11.1 Objectives

- minimize false negatives (legal risk)
- control false positives (operational noise)
- produce auditable match reasoning

## 11.2 Matching Pipeline

1. normalization:
   - case folding, punctuation cleanup, legal suffix normalization, transliteration
2. deterministic pass:
   - exact IDs, strict address-country match, exact alias hits
3. candidate generation:
   - blocking by normalized tokens + country/location signals
4. fuzzy scoring:
   - token/Jaro-Winkler/phonetic/address overlap weighted score
5. decision policy:
   - `MATCH_CONFIRMED`, `REVIEW_REQUIRED`, `NO_MATCH`
6. explanation capture:
   - alias used, score, threshold, matched fields, timestamp

## 11.3 Human-in-the-Loop

- medium-confidence sanctions results enter review queue
- reviewer actions logged with user/time/decision rationale

---

## 12) Retrieval Architecture (RAG + Structured + Graph)

## 12.1 Retrieval Modes

- vector retrieval (Pinecone) for narrative evidence
- lexical constraints inside hybrid retrieval for exact phrases
- SQL retrieval for aggregate metrics and trends
- graph retrieval for multi-hop dependency reasoning
- geospatial retrieval for hazard proximity and historical frequency

## 12.2 Retrieval Pipeline

1. classify query intent
2. select route(s)
3. run parallel retrieval/tools
4. rerank and dedupe evidence
5. validate sufficiency
6. fallback/replan if coverage is low

---

## 13) RAG Router Design (Minimum 4 Routes, Implemented 6)

1. **Financial Route**
   - SEC filings, narrative + tables
2. **Sanctions Route**
   - OFAC/BIS deterministic + fuzzy matching
3. **Commodity/Trade Route**
   - Comtrade structured aggregation
4. **Natural Hazard Route**
   - NOAA geospatial + temporal analytics
5. **Quality/Regulatory Route**
   - FDA letters/alerts + severity classification
6. **Cross-Domain Composite Route**
   - orchestrates multiple routes for Tier-3/Tier-4 queries

---

## 14) LangGraph Agentic Workflow

## 14.1 Graph Nodes

- `init_context`
- `authz_guard`
- `query_classifier`
- `route_planner`
- `financial_node`
- `sanctions_node`
- `trade_node`
- `hazard_node`
- `regulatory_node`
- `kg_traversal_node`
- `evidence_validation_node`
- `risk_scoring_node`
- `answer_generation_node`
- `compliance_output_guard`
- `finalize_response`

## 14.2 Execution Pattern

- parallel route execution for independent evidence pulls
- checkpoint after each stage for resumability
- iterative loop if evidence is insufficient
- fallback to higher-reasoning model for hard queries

---

## 15) Multimodal Handling

## 15.1 Geographic/Spatial

- facility coordinates + hazard layers
- geofencing / radius exposure
- trend windows by severity/event type

## 15.2 Structured Tables

- Comtrade table transformations for numeric analytics
- SEC financial table extraction and trend joins

## 15.3 Entity Lists

- OFAC/BIS structured records with alias graph

---

## 16) Risk Scoring and Cascading Impact

## 16.1 Supplier Node Risk

`NodeRisk = w1*Financial + w2*Sanctions + w3*Hazard + w4*Regulatory + w5*Concentration + w6*Logistics`

## 16.2 Cascading Risk Score (Custom Metric)

`CRS(product) = Σ(DependencyWeight_i * NodeRisk_i * PropagationFactor^(tier_i-1))`

## 16.3 Outputs

- prioritized risk register
- blast-radius view by product line
- mitigation candidates and alternate sourcing paths

---

## 17) Early Warning System

## 17.1 Trigger Inputs

- new OFAC/BIS entries
- new FDA warning/import alert
- new NOAA severe events near critical facilities
- deteriorating financial signals from latest filings
- commodity concentration shifts by source country

## 17.2 Alert Conditions

- sanctions match on monitored supplier
- risk score crosses configurable threshold
- disruption cluster pattern detected (multi-signal coincidence)

## 17.3 Alert Channels

- Slack webhooks
- generic webhook integrations
- dashboard notifications

---

## 18) API and Service Contracts

## 18.1 Core Endpoints (FastAPI)

- `POST /v1/query`
- `POST /v1/risk-assessment/run`
- `GET /v1/risk-assessment/{id}`
- `POST /v1/documents/upload`
- `GET /v1/documents`
- `POST /v1/ingestion/jobs/{source}/run`
- `GET /v1/graph/subgraph`
- `GET /v1/eval/runs`
- `POST /v1/eval/run`
- `GET /v1/audit/sanctions`

## 18.2 Traceability Envelope

Every response includes:

- `correlation_id`
- `query_id`
- `route_plan`
- `source_evidence[]`
- `risk_score_components`
- `confidence`
- `timestamp`

---

## 19) Frontend and UX Requirements

## 19.1 User Interface

- query interface with streaming responses
- inline citations and source panels
- risk dashboard with ranked entities/products
- graph visualization pane
- map visualization of facility-hazard overlays

## 19.2 Admin Dashboard

- tenant/user/role management
- ingestion pipeline monitor
- alert policy management
- evaluation results and ablation charts
- cost/latency/quality telemetry

## 19.3 Document Lifecycle UI

- upload
- validation
- parse/index status
- versioning
- archive/delete controls

---

## 20) Authentication, RBAC, and Multi-Tenant Isolation

## 20.1 Authentication

- Entra ID / OAuth2 with JWT access tokens

## 20.2 Roles

- `admin`
- `analyst`
- `auditor`
- optional `viewer`

## 20.3 Tenant Isolation Controls

- enforce `tenant_id` in API authorization middleware
- Pinecone namespace per tenant
- SQL row-level filtering by tenant_id
- graph partition key by tenant_id
- audit records immutable and tenant-scoped

---

## 21) Observability and Structured Logging

## 21.1 LLM Observability

- LangSmith tracing for:
  - router decision
  - tool calls
  - agent transitions
  - prompt/model usage

## 21.2 Structured Logging

JSON log schema:

- `timestamp`
- `level`
- `service`
- `tenant_id`
- `user_id`
- `correlation_id`
- `query_id`
- `route`
- `latency_ms`
- `token_in`
- `token_out`
- `cost_usd`
- `status`
- `error_code`

## 21.3 Metrics

- route latency p50/p95/p99
- retrieval precision signals
- graph traversal latency
- sanctions match precision/recall
- trade aggregation job time
- failure and retry counts

---

## 22) Compliance Audit Trail (Mandatory)

For each sanctions screening event, log:

- entities screened
- candidate matches
- final match decision
- decision confidence and threshold
- alias/address evidence used
- timestamp
- invoking user and tenant
- model/tool versions used

For each final answer, log provenance:

- source systems touched
- document IDs and graph path IDs
- computations performed
- score inputs and outputs

---

## 23) Evaluation Framework

## 23.1 Required Metrics

- Entity Match Precision/Recall
- Risk Prediction Recall
- Geographic Accuracy
- Graph Traversal Completeness
- Cascading Risk Score accuracy (custom)
- RAGAS metrics:
  - faithfulness
  - answer relevance
  - context precision/recall

## 23.2 Evaluation Tiers

- Tier 1: basic retrieval (7 queries)
- Tier 2: specificity/temporal/versioning (8 queries)
- Tier 3: multi-source cross-reference (8 queries)
- Tier 4: full agentic pipelines (7 queries)

Total required benchmark queries: **30**

## 23.3 Tier 1 Queries

1. Is Huawei Technologies on the OFAC SDN list or BIS Entity List?  
2. What were the top 5 countries exporting rare earth elements in 2024?  
3. List all FDA Warning Letters issued to pharmaceutical manufacturers in India in 2024.  
4. What natural disaster events caused more than $1B in damage in the US Gulf Coast in the last 5 years?  
5. What supply chain risk factors does Apple disclose in their most recent 10-K?  
6. What is China's share of global gallium production?  
7. Show all import alerts currently active for medical devices from China.

## 23.4 Tier 2 Queries

8. Which FDA Warning Letters were issued to API manufacturers in the last 2 years, and what were the common violation categories?  
9. How has TSMC's customer concentration risk disclosure changed across their last 3 annual filings?  
10. What is the geographic concentration of global semiconductor fabrication capacity by country, based on trade flow data?  
11. Compare hurricane frequency/severity in Harris County, TX vs. Hsinchu, Taiwan over the last 20 years.  
12. Which entities were added to the BIS Entity List in 2024, and which countries are most represented?  
13. What is the year-over-year trend in US imports of lithium-ion batteries by source country?  
14. Identify all companies disclosing "single source supplier" risk in their most recent 10-K among top US auto manufacturers.  
15. What is the historical frequency of flooding events in the Rhine River corridor?

## 23.5 Tier 3 Queries

16. Supplier disclosures over 3 filings + sanctions cross-reference with subsidiary aliasing.  
17. Category 4 Gulf hurricane impact zone + facilities + downstream pharma disruption.  
18. Tier 1 auto suppliers with both concentration risk >30% and severe weather location risk.  
19. OFAC/BIS cross-reference with S&P 500 filings using shared names/addresses.  
20. Cobalt flow via DRC + disclosed risks + sanctions overlap.  
21. Top API exporters + FDA warning concentration by country.  
22. NOAA severe events vs semiconductor fab locations from SEC.  
23. FDA warning recipients in last 2 years that also appear as disclosed suppliers.

## 23.6 Tier 4 Queries

24. Full LiDAR chain to raw materials + restricted jurisdiction + hazard zone value exposure.  
25. TSMC 50% production shock cascading model + alternatives sanctions screen + revenue ranking.  
26. China gallium/germanium restriction scenario + S&P 500 product impact + inventory time-to-impact + alternate routes.  
27. Tier 2+ electronics suppliers with going concern/material weakness/customer concentration + hazard/regulatory/downstream impact.  
28. Full risk assessment for US medical device manufacturer across all required dimensions.  
29. Resilience comparison for two automotive competitors across diversification/geography/sanctions/hazard/quality.  
30. Early warning pattern mining validated on historical disruptions.

---

## 24) Ablation Study Plan

Run controlled experiments:

- **A0:** vector-only baseline
- **A1:** + route classification
- **A2:** + structured trade/hazard tools
- **A3:** + knowledge graph traversal
- **A4:** + sanctions entity resolution pipeline
- **A5:** + full LangGraph agentic orchestration

Report by tier:

- answer quality delta
- recall/precision delta
- latency and cost impact

---

## 25) Notifications and Real-Time Alerting

## 25.1 Mandatory Events

- new OFAC/BIS entries detected
- ingestion complete/error
- evaluation run complete summary
- risk threshold breach for monitored entities

## 25.2 Payload Standard

- `event_type`
- `tenant_id`
- `correlation_id`
- `entity_id`
- `severity`
- `summary`
- `evidence_refs[]`
- `timestamp`

---

## 26) Performance and Reliability Targets

## 26.1 SLO Targets

- p95 API response for standard queries: <= 8s
- p95 complex Tier-4 async job first result: <= 90s
- ingestion job success rate: >= 99%
- sanctions matching recall target (compliance set): >= 99%
- dashboard uptime target: >= 99.5%

## 26.2 Resilience

- retries with exponential backoff for external APIs
- dead-letter queues for failed ingestion messages
- idempotent upserts (all sinks)
- blue/green index strategy for Pinecone re-index migrations

---

## 27) CI/CD and Release Controls

## 27.1 Pipeline

- lint and static checks
- unit + integration tests
- evaluation gate (sample benchmark suite)
- security scans
- deploy to staging
- smoke tests
- promote to production

## 27.2 Release Guardrails

- block release if eval regression exceeds threshold
- block release on sanctions resolver precision drop
- rollback playbook with previous image tags + index alias switch

---

## 28) Repository Structure (Recommended)

```text
/
  frontend/
  backend/
    app/
      api/
      agents/
      router/
      retrieval/
      scoring/
      entity_resolution/
      graph/
      ingestion/
      alerts/
      auth/
      observability/
  infra/
    bicep/
    terraform/
  eval/
    datasets/
    runners/
    reports/
  docs/
  SUPPLYCHAINNEXUS_ARCHITECTURE_E2E.md
```

---

## 29) Environment Variables (Minimum)

- `OPENAI_API_KEY`
- `OPENAI_MODEL_SYNTHESIS`
- `OPENAI_MODEL_ROUTER`
- `OPENAI_MODEL_HEAVY_REASONING`
- `OPENAI_EMBEDDING_MODEL`
- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `POSTGRES_URL`
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_KEYVAULT_URI`
- `LANGSMITH_API_KEY`
- `SLACK_WEBHOOK_URL`
- `EVENTGRID_ENDPOINT`
- `EVENTGRID_KEY`

---

## 30) Deliverables Coverage Matrix

## 30.1 Required Deliverables and Coverage

- Deployed web app (live URL): covered in Azure deployment section
- Authentication + RBAC: covered in auth section
- Multi-tenant isolation: covered in isolation section
- Document lifecycle management: covered in frontend + ingestion sections
- React frontend + admin dashboard: covered in UI sections
- Knowledge graph + visualization: covered in graph + UI sections
- RAG router (>=4): covered (6 routes)
- Agentic pipeline: covered (LangGraph workflow)
- Multimodal handling: covered (geo + tables + entity lists)
- Entity resolution for sanctions: covered with deterministic/fuzzy + HITL
- Evaluation framework + RAGAS + custom metric: covered
- Ablation study: covered
- LLM observability: LangSmith + Azure Monitor
- Slack/webhook alerts: covered
- Structured logs + correlation IDs: covered
- GitHub docs: this blueprint + implementation docs plan
- Demo video/walkthrough: included in deadline plan

---

## 31) Execution Plan to April 18, 2026

## 31.1 Daily Plan

- **April 8:** finalize architecture + schemas + repo setup
- **April 9:** SEC + OFAC/BIS ingestion pipelines
- **April 10:** SEC parsing/chunking/indexing + citations metadata
- **April 11:** sanctions entity resolution + compliance audit log service
- **April 12:** Comtrade + NOAA + FDA ingestion and normalization
- **April 13:** Neo4j graph build + traversal APIs
- **April 14:** LangGraph router + specialist agents + checkpoints
- **April 15:** cascading risk scoring + tier-3/4 query orchestration
- **April 16:** full evaluation harness + RAGAS + ablations
- **April 17:** auth/RBAC, multitenancy hardening, alerts, observability
- **April 18:** production deployment, final QA, docs, and demo recording

## 31.2 Critical Path

- sanctions resolver
- graph traversal completeness
- composite router stability
- evaluation gate pass rate

---

## 32) Demo Script (Final Walkthrough)

1. architecture overview  
2. ingestion lifecycle status  
3. Tier-1 and Tier-2 query samples  
4. Tier-3 cross-source correlation sample  
5. Tier-4 cascading risk scenario  
6. graph view + map hazard overlay  
7. sanctions audit log trace  
8. evaluation dashboard + ablation results  
9. alert trigger demonstration  

---

## 33) Risks and Mitigations

- external API instability -> retries + cache + snapshot fallbacks
- sanctions matching false negatives -> strict thresholds + HITL queue
- graph incompleteness -> traversal validation tests + coverage metrics
- ingestion lag -> scheduled jobs + incremental updates + alerting
- deadline risk -> strict critical-path execution and daily checkpoints

---

## 34) Sources and References

- Project brief:  
  https://github.com/fnusatvik07/rag-architect-capstone/blob/main/projects/supplychainnexus.md
- Architecture guide (repo):  
  https://github.com/fnusatvik07/rag-architect-capstone/blob/main/web/src/data/architecture.ts
- RAG technology landscape (repo):  
  https://github.com/fnusatvik07/rag-architect-capstone/blob/main/RAG_TECHNOLOGY_LANDSCAPE_2026.md
- OpenAI embeddings guide:  
  https://developers.openai.com/api/docs/guides/embeddings
- OpenAI embeddings endpoint:  
  https://api.openai.com/v1/embeddings
- OpenAI models endpoint:  
  https://api.openai.com/v1/models
- Pinecone metadata filtering:  
  https://docs.pinecone.io/guides/search/filter-by-metadata
- Pinecone multitenancy/namespaces:  
  https://docs.pinecone.io/guides/index-data/implement-multitenancy
- Pinecone search overview (hybrid context):  
  https://docs.pinecone.io/guides/search/search-overview
- LangGraph overview:  
  https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph persistence/checkpointing:  
  https://docs.langchain.com/oss/python/langgraph/persistence
- LangSmith observability quickstart:  
  https://docs.langchain.com/langsmith/observability-quickstart
- Azure Container Apps overview:  
  https://learn.microsoft.com/en-us/azure/container-apps/overview
- Azure Container Apps jobs:  
  https://learn.microsoft.com/en-us/azure/container-apps/jobs
- Azure Functions timer trigger:  
  https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer
- Azure Event Grid overview:  
  https://learn.microsoft.com/en-us/azure/event-grid/overview
- Azure Key Vault authentication:  
  https://learn.microsoft.com/en-us/azure/key-vault/general/authentication

---

## 35) Final Note

This blueprint is implementation-ready and aligned with all required capstone constraints, concepts, and deliverables.  
Use this as the master architecture baseline for build execution through **April 18, 2026**.

