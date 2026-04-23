# SupplyChainNexus LangGraph Orchestration And Ingestion Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure SupplyChainNexus so raw datasets live under `data/ingestion`, ingestion code lives under `src/ingestion`, each pipeline is exposed as a LangChain tool, and the entire runtime is orchestrated by a LangGraph `StateGraph` with bounded `fullstack` behavior.

**Architecture:** First separate code from raw data by moving datasets under `data/ingestion` and consolidating the ingestion code into `src/ingestion`. Then add LangChain tool wrappers and typed models around the existing deterministic route internals. Finally replace the current orchestrator with a real LangGraph workflow: structured-output router node, single-route execution path, and a bounded `fullstack` subgraph that accumulates route results and synthesizes the final answer.

**Tech Stack:** Python 3.14, LangGraph, LangChain, OpenAI, PostgreSQL via `psycopg`, Neo4j, `unittest`

---

## File Structure

### Create

- `src/ingestion/sec_edgar.py`
- `src/orchestrator/models.py`
- `src/orchestrator/tools.py`
- `src/orchestrator/graph.py`
- `tests/ingestion/test_cli.py`
- `tests/orchestrator/test_tools.py`
- `tests/orchestrator/test_graph.py`

### Move / Rename

- `src/ingestion_sql/base.py` -> `src/ingestion/base.py`
- `src/ingestion_sql/cli.py` -> `src/ingestion/cli.py`
- `src/ingestion_sql/load_comtrade.py` -> `src/ingestion/load_comtrade.py`
- `src/ingestion_sql/load_fda.py` -> `src/ingestion/load_fda.py`
- `src/ingestion_sql/load_noaa.py` -> `src/ingestion/load_noaa.py`
- `src/ingestion_sql/load_ofac_bis.py` -> `src/ingestion/load_ofac_bis.py`
- `src/ingestion_sql/__init__.py` -> `src/ingestion/__init__.py`

### Modify

- `requirements.txt`
- `pyproject.toml`
- `config.py`
- `run_ingestion_sql.py`
- `run_agentic_router.py`
- `README.md`
- `src/pageindex/cli.py`
- `src/pageindex/pipeline.py`
- `src/sanctions/query.py`
- `src/nlsql/query.py`
- `src/graphrag/query.py`
- `src/orchestrator/__init__.py`
- `src/orchestrator/cli.py`
- `src/orchestrator/contracts.py`
- `src/orchestrator/agent.py`
- `tests/nlsql/test_schema.py`
- `tests/nlsql/test_db.py`
- `tests/ingestion_sql/test_cli.py`
- `tests/ingestion_sql/test_load_comtrade.py`
- `tests/ingestion_sql/test_load_fda.py`
- `tests/ingestion_sql/test_load_noaa.py`
- `tests/ingestion_sql/test_load_ofac_bis.py`
- `tests/orchestrator/test_agent.py`

### Data Moves

- `src/Ingestion/OFAC+BIS_Entity/sdn_data.xlsx` -> `data/ingestion/ofac_bis/sdn_data.xlsx`
- `src/Ingestion/NOAAA_StormEventsDetailsData/StormEvents_details-ftp_v1.0_d1950_c20260323.csv` -> `data/ingestion/noaa/StormEvents_details-ftp_v1.0_d1950_c20260323.csv`
- `src/Ingestion/FDAWarningletters+Importalerts/warning-letters.xlsx` -> `data/ingestion/fda/warning-letters.xlsx`
- `src/Ingestion/Un_comtrad_International_tradedata/TradeData.xlsx` -> `data/ingestion/comtrade/TradeData.xlsx`
- `src/Ingestion/Sec_Edgar10kfillings/extracted_10k_sections.json` -> `data/ingestion/sec/extracted_10k_sections.json`
- `src/Ingestion/Sec_Edgar10kfillings/data_edgarfolder/companies.json` -> `data/ingestion/sec/companies.json`
- `src/Ingestion/Sec_Edgar10kfillings/data_edgarfolder/...` -> `data/ingestion/sec/edgar/...`

## Task 1: Add LangChain Dependencies And Prepare The New Layout

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `config.py`

- [ ] **Step 1: Write the failing orchestrator import test for LangChain-backed routing**

```python
def test_build_router_model_uses_langchain_openai() -> None:
    from orchestrator.tools import build_router_model

    model = build_router_model("gpt-4.1-mini")

    assert model is not None
```

- [ ] **Step 2: Run the targeted orchestrator tests to verify the LangChain helper is missing**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.orchestrator.test_tools`
Expected: FAIL with import or attribute errors because `orchestrator.tools` and LangChain model helpers do not exist yet.

- [ ] **Step 3: Add the minimum required Python dependencies**

```toml
dependencies = [
    "azure-identity",
    "psycopg[binary]",
    "langchain>=0.3.0",
    "langchain-openai>=0.3.0",
]
```

- [ ] **Step 4: Add config helpers for data-root resolution**

```python
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data"
INGESTION_DATA_ROOT = DATA_ROOT / "ingestion"
```

- [ ] **Step 5: Run the focused config test**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_config`
Expected: PASS.

### Task 2: Move Raw Datasets Out Of `src` And Consolidate Ingestion Code Into `src/ingestion`

**Files:**
- Create: `src/ingestion/sec_edgar.py`
- Move: `src/ingestion_sql/*.py` -> `src/ingestion/*.py`
- Modify: `run_ingestion_sql.py`
- Modify: `src/pageindex/cli.py`
- Modify: `src/pageindex/pipeline.py`
- Modify: `tests/nlsql/test_schema.py`
- Modify: `tests/ingestion_sql/test_cli.py`
- Modify: `tests/ingestion_sql/test_load_comtrade.py`
- Modify: `tests/ingestion_sql/test_load_fda.py`
- Modify: `tests/ingestion_sql/test_load_noaa.py`
- Modify: `tests/ingestion_sql/test_load_ofac_bis.py`
- Test: `tests/ingestion/test_cli.py`

- [ ] **Step 1: Write the failing ingestion path test**

```python
def test_selected_sources_point_to_data_ingestion_root(self) -> None:
    specs = selected_sources("all")
    self.assertTrue(all("data/ingestion" in str(spec.relative_path).replace("\\\\", "/") for spec in specs))
```

- [ ] **Step 2: Run the focused ingestion tests to verify current paths still point at `src/Ingestion`**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\ingestion_sql -p 'test*.py'`
Expected: FAIL because source paths and package imports still point at `ingestion_sql` and `src/Ingestion`.

- [ ] **Step 3: Move the raw datasets into `data/ingestion/...` using verified workspace-local `Move-Item` commands**

```powershell
New-Item -ItemType Directory -Force data\ingestion\ofac_bis, data\ingestion\noaa, data\ingestion\fda, data\ingestion\comtrade, data\ingestion\sec | Out-Null
Move-Item -LiteralPath src\Ingestion\OFAC+BIS_Entity\sdn_data.xlsx -Destination data\ingestion\ofac_bis\sdn_data.xlsx
Move-Item -LiteralPath src\Ingestion\NOAAA_StormEventsDetailsData\StormEvents_details-ftp_v1.0_d1950_c20260323.csv -Destination data\ingestion\noaa\StormEvents_details-ftp_v1.0_d1950_c20260323.csv
```

- [ ] **Step 4: Rename the ingestion package and update all imports and path defaults**

```python
SOURCE_SPECS = {
    "ofac_bis": SourceSpec(
        name="ofac_bis",
        table_name=OFAC_BIS_TABLE_NAME,
        conflict_columns=OFAC_BIS_CONFLICT_COLUMNS,
        relative_path=Path("data/ingestion/ofac_bis/sdn_data.xlsx"),
        iterator_factory=iter_ofac_bis_records,
    ),
}
```

- [ ] **Step 5: Run the focused ingestion tests again**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\ingestion_sql -p 'test*.py'`
Expected: PASS.

### Task 3: Wrap Each Route As A LangChain Tool

**Files:**
- Create: `src/orchestrator/models.py`
- Create: `src/orchestrator/tools.py`
- Modify: `src/sanctions/query.py`
- Modify: `src/nlsql/query.py`
- Modify: `src/graphrag/query.py`
- Modify: `src/pageindex/pipeline.py`
- Test: `tests/orchestrator/test_tools.py`

- [ ] **Step 1: Write the failing tool-contract tests**

```python
def test_sanctions_tool_returns_normalized_route_envelope() -> None:
    result = sanctions_tool.invoke({"question": "Is Acme Global sanctioned?", "entity_names": ["Acme Global"]})
    assert result["route"] == "sanctions"
    assert "answer" in result
    assert "provenance" in result
```

- [ ] **Step 2: Run the focused tool tests to verify the tool wrappers do not exist**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.orchestrator.test_tools`
Expected: FAIL because `pageindex_tool`, `sanctions_tool`, `nlsql_tool`, `graphrag_tool`, and `ingestion_tool` do not exist.

- [ ] **Step 3: Add typed models and LangChain `@tool` wrappers around the existing deterministic route functions**

```python
@tool
def nlsql_tool(question: str) -> dict[str, object]:
    """Run exact PostgreSQL analytics for structured supply-chain questions."""
    settings = load_app_config()
    return run_nlsql_query(settings, question)
```

- [ ] **Step 4: Ensure each underlying route emits `status`, `route`, `answer`, `provenance`, `freshness`, `warnings`, and `debug` consistently**

```python
return {
    "status": "ok",
    "question": question,
    "route": "nlsql",
    "answer": answer,
    "evidence": ...,
    "provenance": ...,
    "freshness": ...,
    "warnings": warnings,
    "debug": debug,
}
```

- [ ] **Step 5: Run the route and tool tests**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\sanctions -p 'test*.py'`
Expected: PASS.

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\nlsql -p 'test*.py'`
Expected: PASS.

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.orchestrator.test_tools`
Expected: PASS.

### Task 4: Replace The Current Orchestrator With A Real LangGraph Workflow

**Files:**
- Create: `src/orchestrator/graph.py`
- Modify: `src/orchestrator/agent.py`
- Modify: `src/orchestrator/cli.py`
- Modify: `src/orchestrator/__init__.py`
- Modify: `tests/orchestrator/test_agent.py`
- Create: `tests/orchestrator/test_graph.py`

- [ ] **Step 1: Write the failing graph-routing tests**

```python
def test_graph_routes_single_nlsql_question_to_single_route_node(self) -> None:
    result = run_agentic_query(settings, "Which states had the highest storm damage?")
    self.assertEqual("nlsql", result["selected_pipeline"])
    self.assertEqual(["nlsql"], result["completed_routes"])
```

```python
def test_graph_uses_bounded_fullstack_subgraph_for_cross_source_question(self) -> None:
    result = run_agentic_query(settings, "Which sanctioned entities also appear in FDA warning letters?")
    self.assertEqual("fullstack", result["selected_pipeline"])
    self.assertLessEqual(len(result["completed_routes"]), 4)
```

- [ ] **Step 2: Run orchestrator tests to verify the current custom dispatcher fails the new graph expectations**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\orchestrator -p 'test*.py'`
Expected: FAIL because the current orchestrator is not a `StateGraph` with bounded tool execution.

- [ ] **Step 3: Implement the LangGraph state, structured-output router, single-route path, and `fullstack` subgraph**

```python
builder = StateGraph(OrchestratorState)
builder.add_node("preflight", preflight_node)
builder.add_node("route_question", route_question_node)
builder.add_node("run_single_route", run_single_route_node)
builder.add_node("fullstack_subgraph", fullstack_graph)
builder.add_node("final_synthesis", final_synthesis_node)
builder.add_edge(START, "preflight")
builder.add_edge("preflight", "route_question")
builder.add_conditional_edges("route_question", route_after_decision, {
    "run_single_route": "run_single_route",
    "fullstack_subgraph": "fullstack_subgraph",
})
builder.add_edge("run_single_route", "final_synthesis")
builder.add_edge("fullstack_subgraph", "final_synthesis")
builder.add_edge("final_synthesis", END)
```

- [ ] **Step 4: Preserve production-grade routing behavior**

```python
if not decision.mode or decision.mode not in ALLOWED_PIPELINES:
    decision = heuristic_route(question)
if decision.mode == "fullstack":
    planned_routes = decision.routes[:4]
```

- [ ] **Step 5: Run the orchestrator tests again**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\orchestrator -p 'test*.py'`
Expected: PASS.

### Task 5: Update Launchers, Docs, Benchmark Integration, And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `run_agentic_router.py`
- Modify: `run_ingestion_sql.py`
- Modify: `run_pageindex_pipeline.py`
- Modify: `run_nlsql_query.py`
- Modify: `run_sanctions_query.py`
- Modify: `run_graphrag_query.py`
- Modify: `src/evaluation/runner.py`

- [ ] **Step 1: Write the failing launcher/help test**

```python
def test_run_agentic_router_help_mentions_fullstack_and_langgraph() -> None:
    completed = subprocess.run(
        [sys.executable, "run_agentic_router.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    self.assertIn("fullstack", completed.stdout)
    self.assertIn("LangGraph", completed.stdout)
```

- [ ] **Step 2: Run the launcher smoke command before updating docs**

Run: `.\.venv\Scripts\python.exe .\run_agentic_router.py --help`
Expected: output still reflects the old router wording or misses the ingestion/package cleanup details.

- [ ] **Step 3: Update README and runner docs to reflect `data/ingestion`, `src/ingestion`, LangChain tools, and LangGraph orchestration**

```markdown
## Runtime Architecture

- `LangGraph` is the only orchestration runtime
- `pageindex`, `sanctions`, `nlsql`, `graphrag`, and `ingestion` are wrapped as LangChain tools
- `fullstack` is a bounded LangGraph subgraph for multi-route requests
```

- [ ] **Step 4: Run the full focused verification suite**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\nlsql -p 'test*.py'`
Expected: PASS.

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\ingestion_sql -p 'test*.py'`
Expected: PASS.

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\sanctions -p 'test*.py'`
Expected: PASS.

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\orchestrator -p 'test*.py'`
Expected: PASS.

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests\evaluation -p 'test*.py'`
Expected: PASS.

Run: `.\.venv\Scripts\python.exe .\run_agentic_router.py --help`
Expected: exit `0`.

Run: `.\.venv\Scripts\python.exe .\run_ingestion_sql.py --help`
Expected: exit `0`.

## Self-Review

### Spec coverage

- data/code split is implemented by Task 2
- LangChain tool wrappers are implemented by Task 3
- LangGraph-only orchestration is implemented by Task 4
- production-grade bounds, fallbacks, and docs are implemented by Tasks 4 and 5

### Placeholder scan

- no `TBD`, `TODO`, or deferred implementation markers remain
- all commands, files, and architecture changes are concrete

### Type consistency

- route envelopes consistently expose `status`, `route`, `answer`, `provenance`, `freshness`, `warnings`, and `debug`
- orchestrator graph state consistently uses `planned_routes`, `completed_routes`, and `route_results`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-23-supplychainnexus-langgraph-ingestion-restructure.md`.

Because the user already requested immediate implementation, proceed with **Inline Execution** using `superpowers:executing-plans`.
