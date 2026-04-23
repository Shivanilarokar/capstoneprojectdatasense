# OpenAI NL-SQL Postgres Chat Design

**Date:** 2026-04-22

**Goal**

Build a production-minded NL-SQL pipeline that lets users ask natural-language analytical questions over four PostgreSQL-backed datasets:
- OFAC/BIS sanctions entities
- NOAA storm events
- FDA warning letters
- Comtrade trade flows

The system must support both single-source and cross-source analytical questions, generate SQL with OpenAI from live schema context, execute the SQL safely, and return a natural-language answer.

## Problem Statement

The current repository has four source ingestion paths into PostgreSQL, but the `nlsql` layer only supports one hardcoded query shape for Comtrade. That is not sufficient for chat-style analytics over the full dataset estate. The missing capability is an end-to-end NL-to-SQL runtime that:
- understands live PostgreSQL schema
- uses OpenAI to generate SQL dynamically
- validates generated SQL before execution
- executes queries in read-only mode
- retries once on SQL-generation errors
- converts result rows into a natural-language answer

## Scope

### In Scope

- OpenAI-driven SQL generation over the four approved PostgreSQL source tables
- Single-source analytical questions
- Cross-source analytical questions across multiple approved tables
- Runtime schema introspection for prompt construction
- SQL validation and execution guardrails
- One repair retry using database error feedback
- Natural-language answer synthesis from returned rows
- Unit tests for safety-critical and orchestration-critical behavior

### Out of Scope

- Frontend chat UI
- Conversation memory across turns
- Chart rendering
- Dashboarding and query history UI
- RBAC and tenant-scoped auth policy beyond current `tenant_id` filtering
- Non-PostgreSQL backends
- LangGraph orchestration integration beyond the standalone `nlsql` route

## Data Model

The NL-SQL engine will operate only on these approved tables:

- `source_ofac_bis_entities`
- `source_noaa_storm_events`
- `source_fda_warning_letters`
- `source_comtrade_flows`

All queries must include tenant filtering through `tenant_id` where that column exists.

## Architecture

The `nlsql` package will become a five-stage pipeline.

### 1. Schema Introspection

The runtime loads table, column, and type metadata from PostgreSQL for the approved source tables. The metadata is normalized into a compact schema summary for prompting. The introspection layer must be deterministic and small enough to fit comfortably into an LLM prompt.

Responsibilities:
- query `information_schema` and/or PostgreSQL catalogs
- collect table names, column names, types, nullability
- expose only approved tables
- optionally cache schema during one process run

### 2. SQL Generation

The OpenAI model receives:
- the user question
- the allowed schema summary
- explicit SQL generation instructions
- hard safety instructions

The model returns structured JSON with:
- reasoning summary
- referenced tables
- SQL text
- optional ambiguity flag

The generation prompt will instruct the model to:
- produce PostgreSQL SQL only
- use only approved tables and columns
- include joins only when justified by schema semantics
- prefer aggregation and filters for analytics
- avoid destructive or administrative SQL

### 3. SQL Validation

Generated SQL is validated before execution.

Validation rules:
- allow only `SELECT` or `WITH ... SELECT`
- allow one statement only
- reject comments and stacked statements
- reject `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `COPY`, `CALL`, `DO`
- reject references to non-approved tables
- require `tenant_id` filtering for tables that contain `tenant_id`
- enforce row limits for unbounded result sets

This layer is the primary production safety boundary. Prompt instructions are not considered sufficient protection by themselves.

### 4. Safe Execution

Validated SQL runs in PostgreSQL with a read-only execution profile.

Execution rules:
- read-only connection/session behavior
- short statement timeout
- bounded row return size
- explicit error capture
- one repair retry if the SQL fails

The repair retry feeds the exact PostgreSQL error plus the original schema summary and question back to OpenAI, asking for a corrected SQL query under the same constraints.

### 5. Answer Synthesis

The OpenAI model receives:
- the original question
- the SQL that was executed
- column names
- returned rows or summary rows

It returns a natural-language answer that:
- answers the user directly
- cites quantitative findings from the result rows
- clearly says when the result set is empty
- clearly says when the available data is insufficient

## Module Plan

The existing `nlsql` package will be expanded with these responsibilities.

- `src/nlsql/db.py`
  PostgreSQL connection handling, credential acquisition, and connection policy.

- `src/nlsql/schema.py`
  Static bootstrap DDL plus helper utilities for approved-table metadata.

- `src/nlsql/schema_introspection.py`
  Live PostgreSQL schema inspection for approved tables.

- `src/nlsql/models.py`
  Structured runtime objects for schema summaries, generation results, validation results, and final query results.

- `src/nlsql/prompting.py`
  Prompt builders for SQL generation, SQL repair, and answer synthesis.

- `src/nlsql/validation.py`
  SQL safety checks and allowed-table enforcement.

- `src/nlsql/executor.py`
  Safe execution, statement timeout, bounded rows, and retry behavior.

- `src/nlsql/query.py`
  End-to-end orchestration across introspection, generation, validation, execution, repair, and answer synthesis.

- `src/nlsql/cli.py`
  Direct CLI wrapper for standalone question answering.

## OpenAI Integration

OpenAI will be the LLM engine for both SQL generation and answer synthesis.

The implementation must use structured outputs for SQL generation so the runtime is not scraping free-form prose. The expected response shape is:

```json
{
  "reasoning": "short explanation",
  "tables": ["source_comtrade_flows"],
  "sql": "SELECT ...",
  "ambiguity": false
}
```

For answer synthesis, free-form text is acceptable because execution is already complete and safe.

## Cross-Source Query Support

The system must support both:
- single-source analytics, such as FDA-only or NOAA-only questions
- cross-source analytics, such as questions comparing or correlating sanctions, hazards, trade, and warnings

Cross-source support will not depend on hardcoded templates. Instead, the LLM will see the approved schema and produce SQL accordingly. The validator will still enforce table allow-lists and SQL safety rules.

Because these source tables are not fully normalized into a semantic warehouse, some cross-source joins may require heuristic keys like country, state, name, or date-level comparison. The answer synthesizer must be explicit when a cross-source answer is approximate rather than exact.

## Safety Model

This system is intended to be robust, not blindly permissive.

Safety controls:
- approved table allow-list
- single-statement enforcement
- read-only SQL only
- tenant filtering
- row count cap
- timeout cap
- SQL repair limited to one retry
- clean user-facing error messages instead of stack traces

The runtime should capture and return structured debug fields for development, including:
- generated SQL
- validation outcome
- executed SQL
- parameters
- row count
- execution error if any

## Testing Strategy

Tests must cover the production-critical behavior, not only happy paths.

Required test areas:
- schema introspection prompt context formatting
- SQL generation response parsing
- rejection of unsafe SQL
- rejection of non-approved tables
- tenant filter enforcement
- one-retry repair flow
- single-source SQL flow
- cross-source SQL flow
- natural-language answer synthesis formatting
- empty result handling
- execution error handling

## Delivery Target

The implementation is considered complete for this phase when:
- all four source tables are available to NL-SQL
- single-source and cross-source analytical questions work through one pipeline
- SQL is generated by OpenAI from schema context
- generated SQL is validated and executed safely
- answers are returned in natural language
- safety-critical tests pass

## Risks And Mitigations

### Risk: LLM generates unsafe or invalid SQL

Mitigation:
- structured output
- SQL validator
- allow-list checks
- one repair retry

### Risk: Cross-source joins are semantically weak

Mitigation:
- answer synthesis must disclose approximate linkage
- prompt encourages conservative SQL

### Risk: Large result sets or slow queries

Mitigation:
- statement timeout
- row caps
- forced limits for exploratory queries

### Risk: Authentication noise from local Azure credential discovery

Mitigation:
- prefer explicit `PGPASSWORD` when present
- keep fallback credential logic for interactive/local environments

## Implementation Direction

The recommended implementation is:
- OpenAI-driven schema-to-SQL over the approved PostgreSQL schema
- strong runtime safety rails
- minimal additional abstraction beyond what is necessary for production safety and maintainability

This keeps the code simple enough for the current repository while delivering a real end-to-end NL-SQL application over the four datasets.
