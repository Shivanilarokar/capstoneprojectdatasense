# SupplyChainNexus Competition Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge SupplyChainNexus into a competition-ready system with robust `nlsql`, explicit `sanctions`, a five-route orchestrator, and benchmarkable outputs aligned to the approved competition design.

**Architecture:** Promote the stronger PostgreSQL/OpenAI NL-SQL implementation into the main runtime, add a deterministic `sanctions` package over the OFAC/BIS source tables, normalize route outputs with a shared envelope, and upgrade the orchestrator from `pageindex/graphrag/hybrid` to `pageindex/sanctions/nlsql/graphrag/fullstack`. Add a lightweight evaluation package and align the docs and entrypoints to the real competition flow.

**Tech Stack:** Python 3.14, PostgreSQL via `psycopg`, Neo4j, OpenAI Chat Completions, LangGraph, `unittest`, existing CLI entrypoints

---

## File Structure

### New files

- `src/sanctions/__init__.py`: package exports for deterministic sanctions screening
- `src/sanctions/cli.py`: standalone CLI for sanctions screening
- `src/sanctions/matcher.py`: normalization, alias parsing, match scoring, and result construction
- `src/sanctions/query.py`: route entrypoint that loads Postgres data and emits the shared result envelope
- `src/orchestrator/contracts.py`: shared envelope helpers used by route adapters and orchestration
- `src/evaluation/__init__.py`: package marker
- `src/evaluation/benchmarks.py`: benchmark query definitions and expected route metadata
- `src/evaluation/runner.py`: benchmark execution runner
- `src/evaluation/cli.py`: CLI for running the competition benchmark
- `tests/sanctions/test_matcher.py`: deterministic sanctions unit tests
- `tests/sanctions/test_query.py`: sanctions route tests
- `tests/orchestrator/test_agent.py`: route-selection and fullstack orchestration tests
- `tests/evaluation/test_runner.py`: benchmark runner tests

### Modified files

- `src/nlsql/cli.py`
- `src/nlsql/db.py`
- `src/nlsql/executor.py`
- `src/nlsql/planner.py`
- `src/nlsql/prompting.py`
- `src/nlsql/query.py`
- `src/nlsql/schema.py`
- `src/nlsql/synthesizer.py`
- `src/nlsql/__init__.py`
- `src/ingestion_sql/cli.py`
- `src/orchestrator/agent.py`
- `src/orchestrator/cli.py`
- `src/orchestrator/__init__.py`
- `run_agentic_router.py`
- `run_nlsql_query.py`
- `README.md`
- `tests/nlsql/test_query.py`
- `tests/nlsql/test_db.py`
- `tests/nlsql/test_schema.py`

### Adopt from existing feature worktree

- `src/nlsql/models.py`
- `src/nlsql/openai_client.py`
- `src/nlsql/schema_introspection.py`
- `src/nlsql/validation.py`
- `tests/nlsql/test_executor.py`
- `tests/nlsql/test_models.py`
- `tests/nlsql/test_prompting.py`
- `tests/nlsql/test_schema_introspection.py`
- `tests/nlsql/test_validation.py`
- `tests/ingestion_sql/test_cli.py`

### Responsibility boundaries

- `nlsql` owns schema introspection, SQL generation, validation, execution, and answer synthesis.
- `sanctions` owns deterministic entity screening and compliance explanation.
- `orchestrator` owns route selection, envelope normalization, and `fullstack` fusion.
- `evaluation` owns the 30-query competition benchmark and reporting.

### Task 1: Promote Robust NL-SQL Into Main Runtime

**Files:**
- Create: `src/nlsql/models.py`
- Create: `src/nlsql/openai_client.py`
- Create: `src/nlsql/schema_introspection.py`
- Create: `src/nlsql/validation.py`
- Modify: `src/nlsql/cli.py`
- Modify: `src/nlsql/db.py`
- Modify: `src/nlsql/executor.py`
- Modify: `src/nlsql/query.py`
- Modify: `src/ingestion_sql/cli.py`
- Test: `tests/nlsql/test_query.py`
- Test: `tests/nlsql/test_executor.py`
- Test: `tests/nlsql/test_models.py`
- Test: `tests/nlsql/test_prompting.py`
- Test: `tests/nlsql/test_schema_introspection.py`
- Test: `tests/nlsql/test_validation.py`
- Test: `tests/ingestion_sql/test_cli.py`

- [ ] **Step 1: Write the failing tests by adopting the stronger NL-SQL test suite into the main tree**

```python
def test_run_nlsql_query_repairs_validation_failure(self) -> None:
    schema_mock.return_value = (
        {"source_noaa_storm_events": [{"column_name": "tenant_id"}]},
        "Table: source_noaa_storm_events\n- tenant_id (text)\n- state (text)",
    )
    generate_mock.side_effect = [
        SqlGenerationResult(
            reasoning="missing tenant filter",
            tables=["source_noaa_storm_events"],
            sql="SELECT state FROM source_noaa_storm_events",
            ambiguity=False,
        ),
        SqlGenerationResult(
            reasoning="fixed tenant filter",
            tables=["source_noaa_storm_events"],
            sql=(
                "SELECT state, SUM(damage_property_usd) AS total_damage "
                "FROM source_noaa_storm_events "
                "WHERE tenant_id = %(tenant_id)s "
                "GROUP BY state ORDER BY total_damage DESC LIMIT 5"
            ),
            ambiguity=False,
        ),
    ]
    validate_mock.side_effect = [
        ValidationResult(ok=False, reason="SQL must filter source_noaa_storm_events by tenant_id."),
        ValidationResult(ok=True),
    ]
```

- [ ] **Step 2: Run the focused NL-SQL tests to verify they fail against the old implementation**

Run: `.\.venv\Scripts\python.exe -m pytest tests\nlsql tests\ingestion_sql\test_cli.py -q`
Expected: FAIL because the current `nlsql` package does not provide `models`, `validation`, `schema_introspection`, or the repair-path behavior.

- [ ] **Step 3: Promote the robust NL-SQL implementation from the feature worktree into `src/nlsql` and keep the safer executor behavior**

```python
generation = generate_sql(
    settings,
    build_sql_generation_prompt(question=question, schema_text=schema_text),
)
validation = validate_generated_sql(
    generation.sql,
    allowed_tables=allowed_tables,
    tenant_tables=tenant_tables,
)
if not validation.ok:
    generation = generate_sql(
        settings,
        build_sql_repair_prompt(
            question=question,
            schema_text=schema_text,
            bad_sql=generation.sql,
            db_error=validation.reason,
        ),
    )
```

- [ ] **Step 4: Run the focused NL-SQL tests again**

Run: `.\.venv\Scripts\python.exe -m pytest tests\nlsql tests\ingestion_sql\test_cli.py -q`
Expected: PASS with the richer NL-SQL tests green.

- [ ] **Step 5: Commit**

```bash
git add src/nlsql src/ingestion_sql tests/nlsql tests/ingestion_sql/test_cli.py
git commit -m "feat: promote robust nlsql runtime"
```

### Task 2: Add Deterministic Sanctions Route

**Files:**
- Create: `src/sanctions/__init__.py`
- Create: `src/sanctions/cli.py`
- Create: `src/sanctions/matcher.py`
- Create: `src/sanctions/query.py`
- Test: `tests/sanctions/test_matcher.py`
- Test: `tests/sanctions/test_query.py`

- [ ] **Step 1: Write the failing sanctions matcher tests**

```python
def test_screen_entities_finds_primary_and_alias_matches() -> None:
    rows = [
        {
            "source_entity_id": "100",
            "primary_name": "ACME TRADING LLC",
            "aliases": "Acme Trading; Acme Global",
            "sanctions_programs": "SDN",
            "sanctions_type": "Entity",
        }
    ]

    result = screen_entities("Acme Global", rows)

    assert result["matches"][0]["match_type"] == "alias_exact"
    assert result["matches"][0]["matched_name"] == "ACME TRADING LLC"
```

- [ ] **Step 2: Run the sanctions tests to verify they fail before implementation**

Run: `.\.venv\Scripts\python.exe -m pytest tests\sanctions -q`
Expected: FAIL because the `sanctions` package does not exist yet.

- [ ] **Step 3: Implement deterministic screening over `source_ofac_bis_entities` with normalized primary-name and alias matching**

```python
def screen_entities(question: str, rows: list[dict[str, str]]) -> dict[str, object]:
    entities = extract_candidate_entities(question)
    matches = []
    for entity in entities:
        normalized = normalize_name(entity)
        for row in rows:
            primary = normalize_name(row.get("primary_name", ""))
            aliases = [normalize_name(alias) for alias in parse_aliases(row.get("aliases", ""))]
            if normalized and normalized == primary:
                matches.append(build_match(entity, row, "primary_exact"))
            elif normalized and normalized in aliases:
                matches.append(build_match(entity, row, "alias_exact"))
    return {"entities": entities, "matches": matches}
```

- [ ] **Step 4: Run sanctions tests again**

Run: `.\.venv\Scripts\python.exe -m pytest tests\sanctions -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sanctions tests/sanctions
git commit -m "feat: add deterministic sanctions route"
```

### Task 3: Upgrade Orchestrator To Five Routes Plus Fullstack

**Files:**
- Create: `src/orchestrator/contracts.py`
- Modify: `src/orchestrator/agent.py`
- Modify: `src/orchestrator/cli.py`
- Modify: `src/orchestrator/__init__.py`
- Test: `tests/orchestrator/test_agent.py`

- [ ] **Step 1: Write the failing orchestrator tests for route selection and fullstack fan-out**

```python
def test_run_agentic_query_fullstack_combines_selected_routes() -> None:
    with (
        patch("orchestrator.agent.run_sanctions_query") as sanctions_mock,
        patch("orchestrator.agent.run_nlsql_query") as nlsql_mock,
        patch("orchestrator.agent.run_graph_query") as graphrag_mock,
    ):
        sanctions_mock.return_value = {"route": "sanctions", "answer": "matched", "warnings": []}
        nlsql_mock.return_value = {"route": "nlsql", "answer": "counted", "warnings": []}
        graphrag_mock.return_value = {"route": "graphrag", "answer": "cascade", "warnings": []}

        result = run_agentic_query(settings, "Is Acme sanctioned and what cascade risk follows?", options=options)

        assert result["selected_pipeline"] == "fullstack"
        assert "sanctions" in result["routes_executed"]
        assert "nlsql" in result["routes_executed"]
        assert "graphrag" in result["routes_executed"]
```

- [ ] **Step 2: Run the orchestrator tests to verify they fail with the current three-route router**

Run: `.\.venv\Scripts\python.exe -m pytest tests\orchestrator\test_agent.py -q`
Expected: FAIL because `fullstack` and `sanctions` are not supported yet.

- [ ] **Step 3: Implement shared envelopes and the new route selection/fusion logic**

```python
PIPELINE_OPTIONS = ["pageindex", "sanctions", "nlsql", "graphrag", "fullstack"]

def _finalize_fullstack(question: str, route_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    provenance = [route_results[name].get("provenance", {}) for name in route_results]
    warnings = [warning for result in route_results.values() for warning in result.get("warnings", [])]
    answer = _synthesize_fullstack_answer(question, route_results)
    return make_result_envelope(
        question=question,
        route="fullstack",
        answer=answer,
        evidence=route_results,
        provenance={"routes": provenance},
        warnings=warnings,
    )
```

- [ ] **Step 4: Run the orchestrator tests again**

Run: `.\.venv\Scripts\python.exe -m pytest tests\orchestrator\test_agent.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator tests/orchestrator
git commit -m "feat: add competition fullstack orchestrator"
```

### Task 4: Add Evaluation Package And Competition Benchmark

**Files:**
- Create: `src/evaluation/__init__.py`
- Create: `src/evaluation/benchmarks.py`
- Create: `src/evaluation/runner.py`
- Create: `src/evaluation/cli.py`
- Test: `tests/evaluation/test_runner.py`

- [ ] **Step 1: Write the failing benchmark runner tests**

```python
def test_score_run_counts_route_and_provenance_signals() -> None:
    benchmark = {"id": "q1", "expected_route": "sanctions"}
    result = {
        "selected_pipeline": "sanctions",
        "provenance": {"sources": ["source_ofac_bis_entities"]},
        "freshness": {"status": "ok"},
        "warnings": [],
    }

    summary = score_run([{"benchmark": benchmark, "result": result}])

    assert summary["route_accuracy"] == 1.0
    assert summary["provenance_coverage"] == 1.0
    assert summary["freshness_disclosure_rate"] == 1.0
```

- [ ] **Step 2: Run the evaluation tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests\evaluation\test_runner.py -q`
Expected: FAIL because `evaluation` does not exist yet.

- [ ] **Step 3: Implement the benchmark catalog, runner, and scoring summary**

```python
BENCHMARKS = [
    {"id": "q01", "question": "Which sanctioned entities also appear in FDA warning letters?", "expected_route": "fullstack"},
    {"id": "q02", "question": "Which states had the highest storm damage?", "expected_route": "nlsql"},
]

def score_run(records: list[dict[str, object]]) -> dict[str, float]:
    total = len(records) or 1
    route_hits = sum(1 for record in records if record["benchmark"]["expected_route"] == record["result"]["selected_pipeline"])
    provenance_hits = sum(1 for record in records if record["result"].get("provenance"))
    freshness_hits = sum(1 for record in records if record["result"].get("freshness"))
    return {
        "route_accuracy": route_hits / total,
        "provenance_coverage": provenance_hits / total,
        "freshness_disclosure_rate": freshness_hits / total,
    }
```

- [ ] **Step 4: Run the evaluation tests again**

Run: `.\.venv\Scripts\python.exe -m pytest tests\evaluation\test_runner.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evaluation tests/evaluation
git commit -m "feat: add competition benchmark runner"
```

### Task 5: Align Docs And Competition Entrypoints

**Files:**
- Modify: `README.md`
- Modify: `run_agentic_router.py`
- Modify: `run_nlsql_query.py`

- [ ] **Step 1: Write a failing smoke-oriented expectation by documenting the new user-visible entrypoints in README and verifying the CLI help output shape**

```python
def test_parse_args_accepts_fullstack() -> None:
    args = parse_args(["--question", "test", "--force-pipeline", "fullstack"])
    assert args.force_pipeline == "fullstack"
```

- [ ] **Step 2: Run the targeted help/smoke checks**

Run: `.\.venv\Scripts\python.exe .\run_agentic_router.py --help`
Expected: Help text includes `sanctions`, `nlsql`, and `fullstack`.

- [ ] **Step 3: Update README to describe the competition build only**

```markdown
## Competition Routes

- `pageindex`: SEC filing evidence
- `sanctions`: deterministic OFAC/BIS screening
- `nlsql`: exact analytics over PostgreSQL
- `graphrag`: graph-native dependency reasoning
- `fullstack`: multi-route fusion for cross-source questions
```

- [ ] **Step 4: Run the final focused verification suite**

Run: `.\.venv\Scripts\python.exe -m pytest tests\nlsql tests\ingestion_sql tests\sanctions tests\orchestrator tests\evaluation -q`
Expected: PASS.

Run: `.\.venv\Scripts\python.exe .\run_agentic_router.py --help`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add README.md run_agentic_router.py run_nlsql_query.py
git commit -m "docs: align competition entrypoints and README"
```

## Self-Review

### Spec coverage

- Competition route convergence is covered by Tasks 1 through 3.
- Benchmark proof is covered by Task 4.
- Cleanup and user-facing story alignment are covered by Task 5.
- The design’s shared envelope and `fullstack` orchestration are covered by Task 3.

### Placeholder scan

- No `TODO`, `TBD`, or deferred implementation language remains.
- Commands, files, and code skeletons are concrete.

### Type consistency

- Routes use `question`, `route`, `answer`, `evidence`, `provenance`, `freshness`, `warnings`, and `debug`.
- The orchestrator exposes `selected_pipeline` while route envelopes expose `route`; benchmark scoring references the orchestrator output consistently.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-23-supplychainnexus-competition-build.md`.

Because the user already requested immediate implementation, proceed with **Inline Execution** using `superpowers:executing-plans`.
