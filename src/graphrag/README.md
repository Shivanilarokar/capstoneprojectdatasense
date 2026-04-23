# SupplyChainNexus Graph RAG

Graph RAG now has both:

- a sync pipeline from PostgreSQL + SEC extracted sections into Neo4j
- a query pipeline for route-aware graph retrieval and synthesis

Top-level orchestration still lives in `orchestrator`.

For full agentic routing between PageIndex and GraphRAG, use:

```powershell
.\.venv\Scripts\python.exe .\run_agentic_router.py --question "..."
```

## Sync Graph State

Load the ingested source tables and SEC sections into Neo4j:

```powershell
.\.venv\Scripts\python.exe .\run_graphrag_pipeline.py
```

This creates the base graph state used by `graphrag.query`.

## Build Canonical Multi-Tier Topology

Build canonical graph edges on top of already ingested nodes:

```powershell
.\.venv\Scripts\python.exe .\run_graphrag_topology.py
```

This materializes the chain:

`Company -> Tier1 Supplier -> Tier2 Supplier -> Component -> Raw Material -> Source Country -> Hazard Zone -> Sanctions Status`

## Required `.env`

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
GRAPH_TENANT_ID=default
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
SANCTIONS_AUDIT_LOG=src/graphrag/audit_logs/sanctions_screening.jsonl
```

## Run

```powershell
.\.venv\Scripts\python.exe .\run_graphrag_query.py --question "What supply chain risk factors are disclosed in Apple's latest 10-K?"
```

Disable answer synthesis (retrieval summary only):

```powershell
.\.venv\Scripts\python.exe .\run_graphrag_query.py --question "Is Huawei on sanctions lists?" --no-llm
```

## Query Flow

1. GraphRAG route planner selects one or more routes:
   - `financial`: SEC EDGAR financial health (text + table-like evidence extraction)
   - `sanctions`: OFAC/Entity list screening with exact primary/alias matching
   - `trade`: UN Comtrade structured numeric aggregation
   - `hazard`: NOAA geospatial + temporal hazard analytics
   - `regulatory`: FDA quality/regulatory signals with entity cross-check
   - `cascade`: multi-tier path traversal
2. Neo4j retrievers execute per route.
3. Sanctions audit log is written when sanctions route is used.
4. Central generation layer synthesizes final answer (or summary mode with `--no-llm`).
