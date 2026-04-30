## NL-SQL CLI Robustness Design

Date: 2026-04-26

### Goal

Improve the standalone NL-SQL route so it behaves like a reliable analytics chat interface over the four PostgreSQL-backed source tables:

- `source_ofac_sdn_entities`
- `source_noaa_storm_events`
- `source_fda_warning_letters`
- `source_comtrade_flows`

The improved route should produce answer-first terminal output, use stronger LLM prompting with better schema grounding, support controlled cross-source joins, and generate clearer natural-language answers from executed SQL results.

### Non-Goals

- No SEC/PageIndex integration in NL-SQL.
- No GraphRAG or Neo4j changes.
- No full entity-resolution platform.
- No API or frontend changes in this phase.
- No write-capable SQL support.

### Current Problems

The current route is safe but thin:

- CLI prints raw JSON instead of answer-first text.
- Prompt quality is minimal and does not provide route-specific guidance or few-shot examples.
- There is no query classification layer before SQL generation.
- Cross-source joins rely entirely on the LLM improvising SQL.
- Result post-processing is weak for dates, currency, ratios, and evidence display.
- Answer synthesis has no strict output contract.

### Recommended Architecture

Keep the current pipeline shape:

`question -> schema introspection -> SQL generation -> validation -> execution -> answer synthesis`

Add four focused layers around it:

1. A deterministic query classifier before SQL generation.
2. A stronger prompt builder with route-aware few-shot examples.
3. A small cross-source query helper layer for safe canonical joins.
4. A presentation layer that formats results and prints answer-first CLI output.

This preserves the existing safety model while making the route much more usable.

### Target User Experience

Default CLI output should be plain text:

- `Question`
- `Answer`
- `How It Was Computed`
- `Evidence`

Example:

```text
Question
Which states had the highest total property damage?

Answer
Texas had the highest total property damage in the loaded NOAA storm events, followed by Florida and Louisiana.

How It Was Computed
Summed `damage_property_usd` by `state` from `source_noaa_storm_events` for the active tenant and ranked states by descending total damage.

Evidence
1. Texas | $1,200,000
2. Florida | $950,000
3. Louisiana | $840,000
```

Debug mode should remain available via `--debug` and include:

- classifier result
- generated SQL
- validation outcome
- execution metadata
- raw rows

### Component Design

#### 1. Query Classification

Add a lightweight deterministic classifier that maps a question into one of:

- `weather`
- `trade`
- `fda`
- `sanctions`
- `cross_source`
- `unsupported`

Classification should use keywords and table/domain signals, not an LLM call. This keeps classification cheap, explainable, and testable.

Examples:

- `storm`, `damage`, `hurricane`, `state`, `event` -> `weather`
- `export`, `import`, `trade`, `reporter`, `partner`, `HS code` -> `trade`
- `warning letter`, `FDA`, `issuing office`, `severity` -> `fda`
- `sanction`, `SDN`, `OFAC`, `entity list`, `program` -> `sanctions`
- questions combining FDA and OFAC naming or mentioning multiple source families -> `cross_source`

The classifier result should influence prompt construction and evidence formatting.

#### 2. Prompting Upgrade

The generation prompt should be rebuilt around:

- the approved schema only
- the classified route
- route-specific query guidance
- few-shot examples for each route
- explicit SQL safety rules
- explicit tenant filtering rules
- explicit aggregation and formatting expectations

The prompt must tell the LLM:

- use only listed columns
- never invent columns or tables
- keep SQL to a single read-only statement
- include tenant filters for every tenant-scoped table
- prefer canonical join helpers for cross-source questions

Few-shot examples should be included for:

- NOAA aggregation by state and event type
- Comtrade exporter/importer ranking
- FDA company-level warning counts and severity breakdowns
- OFAC sanctions program counts and nationality aggregation
- FDA <-> OFAC company-name matching through canonical helpers

Repair prompts should inherit the same route context and examples.

#### 3. Schema Grounding

Continue using live schema introspection from PostgreSQL, but improve how schema is passed into prompts:

- group columns by table
- highlight the route-relevant tables first
- include data types
- explicitly identify join helper views if present

This reduces hallucinated SQL and keeps the LLM grounded in the real database state.

#### 4. Cross-Source Join Helpers

Add canonical SQL-side helpers for the simplest supported cross-source questions.

This phase should support:

- FDA warning letters matched against OFAC SDN entities by normalized company name

The join helper should normalize names using SQL-safe transforms such as:

- lowercase
- strip punctuation
- collapse whitespace
- remove common corporate suffixes where reasonable

This should be exposed through a reusable helper view or canonical SQL fragment so the LLM joins against a predictable surface instead of improvising name cleaning each time.

Initial supported cross-source pattern:

- `Which companies appear in both FDA warning letters and the OFAC SDN list?`

This is intentionally narrow. Phase 1 will support deterministic normalized-name matching only and will not attempt fuzzy, address-based, or alias-heavy entity resolution.

#### 5. Execution and Safety

Keep the current safeguards:

- approved-table allowlist
- tenant filter enforcement
- read-only cursor
- statement timeout
- row cap
- one validation repair loop
- one execution repair loop

Add clearer unsupported-question handling:

- if the classifier cannot map the question reliably, return a concise user-facing message rather than attempting weak SQL generation

#### 6. Result Post-Processing

Before answer synthesis, shape raw rows into a presentation-friendly form:

- currency fields -> `$1,234,567`
- percentages/ratios -> `12.5%`
- dates -> ISO or readable date form
- large floats -> rounded appropriately
- evidence rows -> compact table-like lines

This layer should not change the raw execution rows. It should create a derived presentation object for answer generation and CLI rendering.

#### 7. Answer Synthesis

Keep answer generation LLM-based, but enforce a stricter contract:

- short direct summary first
- one-sentence computation explanation
- compact evidence section
- no claims beyond the returned rows
- no invented business interpretation

If row count is zero, the answer should say no matching rows were found and avoid speculative explanation.

### File-Level Plan

Primary files to change:

- `src/nlsql/cli.py`
  - add answer-first terminal rendering
  - add `--debug`

- `src/nlsql/query.py`
  - orchestrate classifier, prompt building, helper selection, post-processing, and answer rendering

- `src/nlsql/prompting.py`
  - replace thin prompts with route-aware prompts and few-shot examples

- `src/nlsql/openai_client.py`
  - keep LLM usage here, but ensure structured outputs are enforced for SQL generation

New likely modules:

- `src/nlsql/classifier.py`
  - deterministic route classification

- `src/nlsql/examples.py`
  - few-shot SQL examples grouped by route

- `src/nlsql/joins.py`
  - canonical cross-source SQL helper views or fragments

- `src/nlsql/presentation.py`
  - result formatting and answer-first text rendering

- `src/nlsql/answering.py`
  - stricter answer prompt builder and fallback answer handling

Schema helper to add:

- a canonical helper view for normalized FDA <-> OFAC company matching

### Data Flow After Improvement

1. CLI receives question.
2. Classifier assigns route.
3. Live schema is introspected.
4. Prompt builder selects route-aware examples and schema emphasis.
5. LLM generates SQL.
6. Validator enforces safety and tenant rules.
7. Executor runs SQL read-only against PostgreSQL.
8. If needed, one repair pass is attempted.
9. Result formatter derives evidence rows and formatted values.
10. LLM generates a constrained natural-language answer from question plus formatted evidence.
11. CLI prints answer-first text.
12. If `--debug` is set, raw internals are printed after the human-facing answer.

### Testing Strategy

Add or update tests for:

- deterministic classifier routing
- route-aware prompt generation
- cross-source helper selection
- output rendering in normal mode and debug mode
- answer formatting for zero rows, one row, and multi-row cases
- existing validation and execution safety behavior

Key regression coverage:

- non-approved tables still rejected
- missing tenant filter still rejected
- execution repair still works
- cross-source FDA/OFAC question produces canonical join SQL

### Risks

- Over-constraining prompts can make SQL too rigid.
- Under-constraining cross-source joins can produce weak matches.
- LLM answer generation can still overstate evidence if prompts are vague.

Mitigations:

- keep deterministic classifier outside the LLM
- keep join support narrow in phase 1
- require answer generation to rely only on returned rows
- preserve `--debug` so generated SQL remains inspectable

### Success Criteria

The phase is successful when:

- `run_nlsql_query.py` defaults to answer-first terminal output
- questions over NOAA, Comtrade, FDA, and OFAC are answered more consistently
- simple FDA <-> OFAC cross-source questions work through canonical join helpers
- generated SQL remains tenant-scoped and read-only
- the LLM receives stronger schema context and few-shot examples
- the route feels like a natural-language analytics assistant instead of a raw JSON debug tool
