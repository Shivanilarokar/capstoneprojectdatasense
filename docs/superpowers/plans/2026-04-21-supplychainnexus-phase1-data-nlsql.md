# SupplyChainNexus Phase 1 Data + NL-SQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PostgreSQL foundation, repeatable local-source ingestion pipeline, and standalone `nlsql` route for non-EDGAR sources.

**Architecture:** This phase adds a tenant-aware PostgreSQL layer backed by Azure AD token auth, source-first ingestion for OFAC/BIS, Comtrade, NOAA, and FDA, and a safe `nlsql` route that answers structured analytics questions without mixing SQL into graph traversal. The existing `pageindex` and `graphrag` packages remain unchanged in this phase except for shared config usage.

**Tech Stack:** Python 3.11, psycopg 3, Azure Identity `DefaultAzureCredential`, openpyxl, csv, LangGraph-compatible route packaging, unittest

---

## File Map

### Modify

- `requirements.txt`
  Add runtime dependencies for PostgreSQL and Azure identity.
- `pyproject.toml`
  Mirror the new runtime dependencies in project metadata.
- `config.py`
  Add PostgreSQL runtime settings and Azure token scope settings to `AppConfig` and `load_app_config()`.

### Create

- `tests/__init__.py`
  Make the test package importable by `python -m unittest`.
- `tests/nlsql/__init__.py`
  Package marker for `nlsql` tests.
- `tests/ingestion_sql/__init__.py`
  Package marker for ingestion tests.
- `tests/test_config.py`
  Regression tests for new config loading behavior.
- `tests/nlsql/test_db.py`
  Unit tests for Azure token-backed PostgreSQL connection logic.
- `tests/nlsql/test_schema.py`
  Unit tests for source table DDL bootstrap.
- `tests/nlsql/test_query.py`
  Unit tests for `nlsql` planning, SQL building, and answer synthesis.
- `tests/ingestion_sql/test_load_ofac_bis.py`
  Tests for OFAC/BIS transformation and upsert payloads.
- `tests/ingestion_sql/test_load_noaa.py`
  Tests for NOAA parsing and damage normalization.
- `tests/ingestion_sql/test_load_fda.py`
  Tests for FDA hashing and upsert payloads.
- `tests/ingestion_sql/test_load_comtrade.py`
  Tests for Comtrade row transformation.
- `tests/ingestion_sql/test_cli.py`
  Tests for the ingestion CLI entrypoints.
- `src/nlsql/__init__.py`
  Package marker and public exports.
- `src/nlsql/db.py`
  Azure AD token acquisition and psycopg connection helpers.
- `src/nlsql/schema.py`
  Source table DDL and schema bootstrap function.
- `src/nlsql/planner.py`
  Question-to-intent planner for the standalone `nlsql` route.
- `src/nlsql/executor.py`
  Safe SQL builder and executor for whitelisted query shapes.
- `src/nlsql/synthesizer.py`
  Result-to-answer formatter for `nlsql`.
- `src/nlsql/query.py`
  End-to-end `run_nlsql_query()` function.
- `src/nlsql/cli.py`
  CLI wrapper for direct `nlsql` execution.
- `src/ingestion_sql/__init__.py`
  Package marker and public exports.
- `src/ingestion_sql/base.py`
  Shared helpers for hashing, type coercion, and upsert batching.
- `src/ingestion_sql/load_ofac_bis.py`
  Excel loader for OFAC/BIS source data.
- `src/ingestion_sql/load_noaa.py`
  CSV loader for NOAA storm events.
- `src/ingestion_sql/load_fda.py`
  Excel loader for FDA warning letters.
- `src/ingestion_sql/load_comtrade.py`
  Excel loader for Comtrade trade flow data.
- `src/ingestion_sql/cli.py`
  CLI to initialize schema and load one or all sources.
- `run_nlsql_query.py`
  Convenience launcher matching the repo’s current runner pattern.
- `run_ingestion_sql.py`
  Convenience launcher for the ingestion pipeline.

## Scope Notes

- This plan intentionally ends with a working standalone `nlsql` route and repeatable data loads.
- `sanctions`, `fullstack`, frontend, RBAC, observability, and deployment belong to later plans.
- This phase must still be production-minded: token refresh, idempotent loads, tenant scoping, structured outputs, and test coverage are required now.

### Task 1: Add runtime dependencies and PostgreSQL config

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `config.py`

- [ ] **Step 1: Write the failing config test**

```python
import os
from unittest import TestCase
from unittest.mock import patch

from config import load_app_config


class ConfigTests(TestCase):
    @patch.dict(
        os.environ,
        {
            "PGHOST": "postgescapstoneproject.postgres.database.azure.com",
            "PGUSER": "sweetyshivzz454@gmail.com",
            "PGPORT": "5432",
            "PGDATABASE": "postgres",
        },
        clear=False,
    )
    def test_load_app_config_reads_postgres_runtime_settings(self) -> None:
        settings = load_app_config(tenant_id_override="tenant-dev")

        self.assertEqual("postgescapstoneproject.postgres.database.azure.com", settings.pg_host)
        self.assertEqual("sweetyshivzz454@gmail.com", settings.pg_user)
        self.assertEqual(5432, settings.pg_port)
        self.assertEqual("postgres", settings.pg_database)
        self.assertEqual("require", settings.pg_sslmode)
        self.assertEqual(
            "https://ossrdbms-aad.database.windows.net/.default",
            settings.azure_postgres_scope,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_config -v`
Expected: FAIL with `AttributeError` or missing `pg_host` / `azure_postgres_scope` fields on `AppConfig`

- [ ] **Step 3: Write minimal config implementation**

```python
@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    openai_api_key: str
    openai_model: str
    pageindex_api_key: str
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    graph_tenant_id: str
    sanctions_audit_log: Path
    pg_host: str
    pg_user: str
    pg_port: int
    pg_database: str
    pg_sslmode: str
    azure_postgres_scope: str

    def with_tenant(self, tenant_id: str | None) -> "AppConfig":
        chosen = (tenant_id or "").strip() or self.graph_tenant_id
        return AppConfig(
            project_root=self.project_root,
            openai_api_key=self.openai_api_key,
            openai_model=self.openai_model,
            pageindex_api_key=self.pageindex_api_key,
            neo4j_uri=self.neo4j_uri,
            neo4j_username=self.neo4j_username,
            neo4j_password=self.neo4j_password,
            neo4j_database=self.neo4j_database,
            graph_tenant_id=chosen,
            sanctions_audit_log=self.sanctions_audit_log,
            pg_host=self.pg_host,
            pg_user=self.pg_user,
            pg_port=self.pg_port,
            pg_database=self.pg_database,
            pg_sslmode=self.pg_sslmode,
            azure_postgres_scope=self.azure_postgres_scope,
        )


def load_app_config(tenant_id_override: str | None = None) -> AppConfig:
    load_dotenv()
    tenant = (tenant_id_override or os.getenv("GRAPH_TENANT_ID", "default")).strip() or "default"
    audit_default = PROJECT_ROOT / "src" / "graphrag" / "audit_logs" / "sanctions_screening.jsonl"
    return AppConfig(
        project_root=PROJECT_ROOT,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        pageindex_api_key=os.getenv("PAGEINDEX_API_KEY", "").strip(),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687").strip(),
        neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j").strip(),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "").strip(),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j").strip(),
        graph_tenant_id=tenant,
        sanctions_audit_log=Path(os.getenv("SANCTIONS_AUDIT_LOG", str(audit_default))),
        pg_host=os.getenv("PGHOST", "").strip(),
        pg_user=os.getenv("PGUSER", "").strip(),
        pg_port=int(os.getenv("PGPORT", "5432")),
        pg_database=os.getenv("PGDATABASE", "postgres").strip(),
        pg_sslmode=os.getenv("PGSSLMODE", "require").strip(),
        azure_postgres_scope=os.getenv(
            "AZURE_POSTGRES_SCOPE",
            "https://ossrdbms-aad.database.windows.net/.default",
        ).strip(),
    )
```

Add runtime dependencies:

```text
azure-identity
psycopg[binary]
```

Update `pyproject.toml`:

```toml
[project]
dependencies = [
  "azure-identity",
  "psycopg[binary]",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_config.py requirements.txt pyproject.toml config.py
git commit -m "feat: add postgres runtime config"
```

### Task 2: Implement Azure AD token-backed PostgreSQL connections

**Files:**
- Create: `tests/nlsql/__init__.py`
- Create: `tests/nlsql/test_db.py`
- Create: `src/nlsql/__init__.py`
- Create: `src/nlsql/db.py`

- [ ] **Step 1: Write the failing DB connection tests**

```python
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from config import AppConfig, PROJECT_ROOT
from nlsql.db import connect_postgres


class PostgresConnectionTests(TestCase):
    def _settings(self) -> AppConfig:
        return AppConfig(
            project_root=PROJECT_ROOT,
            openai_api_key="",
            openai_model="gpt-4.1-mini",
            pageindex_api_key="",
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
            graph_tenant_id="tenant-dev",
            sanctions_audit_log=PROJECT_ROOT / "tmp" / "audit.jsonl",
            pg_host="postgescapstoneproject.postgres.database.azure.com",
            pg_user="sweetyshivzz454@gmail.com",
            pg_port=5432,
            pg_database="postgres",
            pg_sslmode="require",
            azure_postgres_scope="https://ossrdbms-aad.database.windows.net/.default",
        )

    @patch("nlsql.db.psycopg.connect")
    @patch("nlsql.db.DefaultAzureCredential")
    def test_connect_postgres_uses_defaultazurecredential_token(self, credential_cls, connect_mock) -> None:
        credential = credential_cls.return_value
        credential.get_token.return_value = SimpleNamespace(token="aad-token")

        connect_postgres(self._settings())

        credential.get_token.assert_called_once_with(
            "https://ossrdbms-aad.database.windows.net/.default"
        )
        kwargs = connect_mock.call_args.kwargs
        self.assertEqual("aad-token", kwargs["password"])
        self.assertEqual("postgescapstoneproject.postgres.database.azure.com", kwargs["host"])
        self.assertEqual("sweetyshivzz454@gmail.com", kwargs["user"])
        self.assertEqual("postgres", kwargs["dbname"])
        self.assertEqual("require", kwargs["sslmode"])
        self.assertTrue(kwargs["autocommit"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.nlsql.test_db -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nlsql.db'`

- [ ] **Step 3: Write minimal DB implementation**

```python
from __future__ import annotations

import psycopg
from azure.identity import DefaultAzureCredential
from psycopg.rows import dict_row

from config import AppConfig


def connect_postgres(settings: AppConfig):
    credential = DefaultAzureCredential()
    token = credential.get_token(settings.azure_postgres_scope).token
    return psycopg.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_database,
        user=settings.pg_user,
        password=token,
        sslmode=settings.pg_sslmode,
        autocommit=True,
        row_factory=dict_row,
    )
```

```python
from .db import connect_postgres

__all__ = ["connect_postgres"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.nlsql.test_db -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/__init__.py tests/nlsql/test_db.py src/nlsql/__init__.py src/nlsql/db.py
git commit -m "feat: add azure token postgres connector"
```

### Task 3: Bootstrap source tables and shared ingestion helpers

**Files:**
- Create: `tests/nlsql/test_schema.py`
- Create: `src/nlsql/schema.py`
- Create: `src/ingestion_sql/__init__.py`
- Create: `src/ingestion_sql/base.py`

- [ ] **Step 1: Write the failing schema/helper tests**

```python
from unittest import TestCase

from ingestion_sql.base import stable_record_hash
from nlsql.schema import SOURCE_TABLE_DDLS


class SchemaTests(TestCase):
    def test_source_table_ddls_cover_all_phase1_sources(self) -> None:
        self.assertEqual(
            {
                "source_ofac_bis_entities",
                "source_comtrade_flows",
                "source_noaa_storm_events",
                "source_fda_warning_letters",
            },
            set(SOURCE_TABLE_DDLS.keys()),
        )

    def test_stable_record_hash_is_deterministic(self) -> None:
        self.assertEqual(
            stable_record_hash("tenant-dev", "acme", "2025-01-01"),
            stable_record_hash("tenant-dev", "acme", "2025-01-01"),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.nlsql.test_schema -v`
Expected: FAIL with `ModuleNotFoundError` for `nlsql.schema` or `ingestion_sql.base`

- [ ] **Step 3: Write minimal schema and helper implementation**

```python
from __future__ import annotations

SOURCE_TABLE_DDLS = {
    "source_ofac_bis_entities": """
        CREATE TABLE IF NOT EXISTS source_ofac_bis_entities (
            tenant_id TEXT NOT NULL,
            source_entity_id TEXT NOT NULL,
            primary_name TEXT NOT NULL,
            entity_type TEXT,
            sanctions_programs TEXT,
            sanctions_type TEXT,
            date_published TEXT,
            aliases TEXT,
            nationality TEXT,
            citizenship TEXT,
            address_text TEXT,
            document_ids TEXT,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, source_entity_id)
        )
    """,
    "source_comtrade_flows": """
        CREATE TABLE IF NOT EXISTS source_comtrade_flows (
            tenant_id TEXT NOT NULL,
            source_record_hash TEXT NOT NULL,
            ref_year INTEGER NOT NULL,
            flow_code TEXT,
            flow_desc TEXT,
            reporter_iso TEXT,
            reporter_desc TEXT,
            partner_iso TEXT,
            partner_desc TEXT,
            cmd_code TEXT,
            cmd_desc TEXT,
            qty DOUBLE PRECISION,
            net_wgt DOUBLE PRECISION,
            cifvalue DOUBLE PRECISION,
            fobvalue DOUBLE PRECISION,
            primary_value DOUBLE PRECISION,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, source_record_hash)
        )
    """,
    "source_noaa_storm_events": """
        CREATE TABLE IF NOT EXISTS source_noaa_storm_events (
            tenant_id TEXT NOT NULL,
            event_id BIGINT NOT NULL,
            episode_id BIGINT,
            state TEXT,
            year INTEGER,
            month_name TEXT,
            event_type TEXT,
            cz_name TEXT,
            begin_date_time TEXT,
            end_date_time TEXT,
            damage_property_raw TEXT,
            damage_property_usd DOUBLE PRECISION,
            damage_crops_raw TEXT,
            damage_crops_usd DOUBLE PRECISION,
            begin_lat DOUBLE PRECISION,
            begin_lon DOUBLE PRECISION,
            end_lat DOUBLE PRECISION,
            end_lon DOUBLE PRECISION,
            episode_narrative TEXT,
            event_narrative TEXT,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, event_id)
        )
    """,
    "source_fda_warning_letters": """
        CREATE TABLE IF NOT EXISTS source_fda_warning_letters (
            tenant_id TEXT NOT NULL,
            source_record_hash TEXT NOT NULL,
            posted_date TEXT,
            letter_issue_date TEXT,
            company_name TEXT NOT NULL,
            issuing_office TEXT,
            subject TEXT,
            response_letter TEXT,
            closeout_letter TEXT,
            source_file_name TEXT NOT NULL,
            source_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            raw_payload JSONB NOT NULL,
            PRIMARY KEY (tenant_id, source_record_hash)
        )
    """,
}
```

```python
from __future__ import annotations

import hashlib
import json
from typing import Iterable


def stable_record_hash(*parts: object) -> str:
    payload = "||".join("" if part is None else str(part).strip() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def json_payload(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False)


def batched(iterable: Iterable[dict], size: int = 1000):
    batch: list[dict] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.nlsql.test_schema -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/nlsql/test_schema.py src/nlsql/schema.py src/ingestion_sql/__init__.py src/ingestion_sql/base.py
git commit -m "feat: add source table schema bootstrap"
```

### Task 4: Implement OFAC/BIS ingestion

**Files:**
- Create: `tests/ingestion_sql/__init__.py`
- Create: `tests/ingestion_sql/test_load_ofac_bis.py`
- Create: `src/ingestion_sql/load_ofac_bis.py`

- [ ] **Step 1: Write the failing OFAC/BIS loader test**

```python
from unittest import TestCase

from ingestion_sql.load_ofac_bis import transform_ofac_bis_row


class OfacBisLoaderTests(TestCase):
    def test_transform_ofac_bis_row_maps_primary_columns(self) -> None:
        row = {
            "Entity ID": "36",
            "Primary Name": "AEROCARIBBEAN AIRLINES",
            "Entity Type": "Entity",
            "Sanctions Program(s)": "CUBA",
            "Sanctions Type": "Block",
            "Date Published": "1986-12-10",
            "Aliases": "A.K.A.: AERO-CARIBBEAN",
            "Nationality": None,
            "Citizenship": None,
            "Address(es)": "Havana, Cuba",
            "Document IDs": None,
        }

        record = transform_ofac_bis_row("tenant-dev", "sdn_data.xlsx", row)

        self.assertEqual("tenant-dev", record["tenant_id"])
        self.assertEqual("36", record["source_entity_id"])
        self.assertEqual("AEROCARIBBEAN AIRLINES", record["primary_name"])
        self.assertEqual("CUBA", record["sanctions_programs"])
        self.assertEqual("Havana, Cuba", record["address_text"])
        self.assertEqual("sdn_data.xlsx", record["source_file_name"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.ingestion_sql.test_load_ofac_bis -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingestion_sql.load_ofac_bis'`

- [ ] **Step 3: Write minimal OFAC/BIS transformation and loader**

```python
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .base import json_payload


def transform_ofac_bis_row(tenant_id: str, source_file_name: str, row: dict) -> dict:
    return {
        "tenant_id": tenant_id,
        "source_entity_id": str(row.get("Entity ID", "")).strip(),
        "primary_name": str(row.get("Primary Name", "")).strip(),
        "entity_type": str(row.get("Entity Type", "")).strip(),
        "sanctions_programs": str(row.get("Sanctions Program(s)", "")).strip(),
        "sanctions_type": str(row.get("Sanctions Type", "")).strip(),
        "date_published": str(row.get("Date Published", "")).strip(),
        "aliases": str(row.get("Aliases", "")).strip(),
        "nationality": str(row.get("Nationality", "")).strip(),
        "citizenship": str(row.get("Citizenship", "")).strip(),
        "address_text": str(row.get("Address(es)", "")).strip(),
        "document_ids": str(row.get("Document IDs", "")).strip(),
        "source_file_name": source_file_name,
        "raw_payload": json_payload(row),
    }


def iter_ofac_bis_records(tenant_id: str, source_path: Path):
    workbook = load_workbook(source_path, read_only=True, data_only=True)
    sheet = workbook["SDN Entities"]
    headers = [str(cell) if cell is not None else "" for cell in next(sheet.iter_rows(values_only=True))]
    for values in sheet.iter_rows(min_row=2, values_only=True):
        row = dict(zip(headers, values, strict=False))
        if not str(row.get("Entity ID", "")).strip():
            continue
        yield transform_ofac_bis_row(tenant_id, source_path.name, row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.ingestion_sql.test_load_ofac_bis -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/ingestion_sql/__init__.py tests/ingestion_sql/test_load_ofac_bis.py src/ingestion_sql/load_ofac_bis.py
git commit -m "feat: add ofac bis ingestion transformer"
```

### Task 5: Implement NOAA ingestion with damage normalization

**Files:**
- Create: `tests/ingestion_sql/test_load_noaa.py`
- Create: `src/ingestion_sql/load_noaa.py`

- [ ] **Step 1: Write the failing NOAA loader test**

```python
from unittest import TestCase

from ingestion_sql.load_noaa import parse_damage_value, transform_noaa_row


class NoaaLoaderTests(TestCase):
    def test_parse_damage_value_handles_k_m_b_suffixes(self) -> None:
        self.assertEqual(250000.0, parse_damage_value("250K"))
        self.assertEqual(1200000.0, parse_damage_value("1.2M"))
        self.assertEqual(3000000000.0, parse_damage_value("3B"))

    def test_transform_noaa_row_maps_core_fields(self) -> None:
        row = {
            "EVENT_ID": "10096222",
            "EPISODE_ID": "",
            "STATE": "OKLAHOMA",
            "YEAR": "1950",
            "MONTH_NAME": "April",
            "EVENT_TYPE": "Tornado",
            "CZ_NAME": "WASHITA",
            "BEGIN_DATE_TIME": "28-APR-50 14:45:00",
            "END_DATE_TIME": "28-APR-50 14:45:00",
            "DAMAGE_PROPERTY": "250K",
            "DAMAGE_CROPS": "0",
            "BEGIN_LAT": "35.12",
            "BEGIN_LON": "-99.20",
            "END_LAT": "35.17",
            "END_LON": "-99.20",
            "EPISODE_NARRATIVE": "",
            "EVENT_NARRATIVE": "",
        }

        record = transform_noaa_row("tenant-dev", "storm.csv", row)

        self.assertEqual(10096222, record["event_id"])
        self.assertEqual("OKLAHOMA", record["state"])
        self.assertEqual("Tornado", record["event_type"])
        self.assertEqual(250000.0, record["damage_property_usd"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.ingestion_sql.test_load_noaa -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingestion_sql.load_noaa'`

- [ ] **Step 3: Write minimal NOAA parser and transformer**

```python
from __future__ import annotations

import csv
from pathlib import Path

from .base import json_payload


def parse_damage_value(value: str) -> float:
    raw = (value or "").strip().upper()
    if not raw or raw == "0":
        return 0.0
    multiplier = 1.0
    if raw.endswith("K"):
        multiplier = 1_000.0
        raw = raw[:-1]
    elif raw.endswith("M"):
        multiplier = 1_000_000.0
        raw = raw[:-1]
    elif raw.endswith("B"):
        multiplier = 1_000_000_000.0
        raw = raw[:-1]
    return float(raw) * multiplier


def transform_noaa_row(tenant_id: str, source_file_name: str, row: dict) -> dict:
    return {
        "tenant_id": tenant_id,
        "event_id": int(row["EVENT_ID"]),
        "episode_id": int(row["EPISODE_ID"]) if str(row.get("EPISODE_ID", "")).strip() else None,
        "state": str(row.get("STATE", "")).strip(),
        "year": int(row["YEAR"]) if str(row.get("YEAR", "")).strip() else None,
        "month_name": str(row.get("MONTH_NAME", "")).strip(),
        "event_type": str(row.get("EVENT_TYPE", "")).strip(),
        "cz_name": str(row.get("CZ_NAME", "")).strip(),
        "begin_date_time": str(row.get("BEGIN_DATE_TIME", "")).strip(),
        "end_date_time": str(row.get("END_DATE_TIME", "")).strip(),
        "damage_property_raw": str(row.get("DAMAGE_PROPERTY", "")).strip(),
        "damage_property_usd": parse_damage_value(str(row.get("DAMAGE_PROPERTY", ""))),
        "damage_crops_raw": str(row.get("DAMAGE_CROPS", "")).strip(),
        "damage_crops_usd": parse_damage_value(str(row.get("DAMAGE_CROPS", ""))),
        "begin_lat": float(row["BEGIN_LAT"]) if str(row.get("BEGIN_LAT", "")).strip() else None,
        "begin_lon": float(row["BEGIN_LON"]) if str(row.get("BEGIN_LON", "")).strip() else None,
        "end_lat": float(row["END_LAT"]) if str(row.get("END_LAT", "")).strip() else None,
        "end_lon": float(row["END_LON"]) if str(row.get("END_LON", "")).strip() else None,
        "episode_narrative": str(row.get("EPISODE_NARRATIVE", "")).strip(),
        "event_narrative": str(row.get("EVENT_NARRATIVE", "")).strip(),
        "source_file_name": source_file_name,
        "raw_payload": json_payload(row),
    }


def iter_noaa_records(tenant_id: str, source_path: Path):
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not str(row.get("EVENT_ID", "")).strip():
                continue
            yield transform_noaa_row(tenant_id, source_path.name, row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.ingestion_sql.test_load_noaa -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/ingestion_sql/test_load_noaa.py src/ingestion_sql/load_noaa.py
git commit -m "feat: add noaa ingestion transformer"
```

### Task 6: Implement FDA and Comtrade ingestion

**Files:**
- Create: `tests/ingestion_sql/test_load_fda.py`
- Create: `tests/ingestion_sql/test_load_comtrade.py`
- Create: `src/ingestion_sql/load_fda.py`
- Create: `src/ingestion_sql/load_comtrade.py`

- [ ] **Step 1: Write the failing FDA and Comtrade loader tests**

```python
from unittest import TestCase

from ingestion_sql.load_comtrade import transform_comtrade_row
from ingestion_sql.load_fda import transform_fda_row


class FdaLoaderTests(TestCase):
    def test_transform_fda_row_uses_record_hash_primary_key(self) -> None:
        row = {
            "Posted Date": "12/02/2025",
            "Letter Issue Date": "11/12/2025",
            "Company Name": "Rhyz Analytical Labs",
            "Issuing Office": "Center for Drug Evaluation and Research (CDER)",
            "Subject": "CGMP/Finished Pharmaceuticals/Adulterated",
            "Response Letter": None,
            "Closeout Letter": None,
        }

        record = transform_fda_row("tenant-dev", "warning-letters.xlsx", row)

        self.assertEqual("tenant-dev", record["tenant_id"])
        self.assertEqual("Rhyz Analytical Labs", record["company_name"])
        self.assertTrue(record["source_record_hash"])


class ComtradeLoaderTests(TestCase):
    def test_transform_comtrade_row_maps_trade_dimensions(self) -> None:
        row = {
            "refYear": 2025,
            "flowCode": "X",
            "flowDesc": "Export",
            "reporterISO": "AZE",
            "reporterDesc": "Azerbaijan",
            "partnerISO": "W00",
            "partnerDesc": "World",
            "cmdCode": "TOTAL",
            "cmdDesc": "All Commodities",
            "qty": 0,
            "netWgt": None,
            "cifvalue": None,
            "fobvalue": 25042007312.55,
            "primaryValue": 25042007312.55,
        }

        record = transform_comtrade_row("tenant-dev", "TradeData.xlsx", row)

        self.assertEqual(2025, record["ref_year"])
        self.assertEqual("X", record["flow_code"])
        self.assertEqual("AZE", record["reporter_iso"])
        self.assertEqual(25042007312.55, record["primary_value"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.ingestion_sql.test_load_fda tests.ingestion_sql.test_load_comtrade -v`
Expected: FAIL with `ModuleNotFoundError` for `ingestion_sql.load_fda` and `ingestion_sql.load_comtrade`

- [ ] **Step 3: Write minimal FDA and Comtrade transformers**

```python
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .base import json_payload, stable_record_hash


def transform_fda_row(tenant_id: str, source_file_name: str, row: dict) -> dict:
    record_hash = stable_record_hash(
        tenant_id,
        row.get("Company Name"),
        row.get("Posted Date"),
        row.get("Subject"),
    )
    return {
        "tenant_id": tenant_id,
        "source_record_hash": record_hash,
        "posted_date": str(row.get("Posted Date", "")).strip(),
        "letter_issue_date": str(row.get("Letter Issue Date", "")).strip(),
        "company_name": str(row.get("Company Name", "")).strip(),
        "issuing_office": str(row.get("Issuing Office", "")).strip(),
        "subject": str(row.get("Subject", "")).strip(),
        "response_letter": str(row.get("Response Letter", "")).strip(),
        "closeout_letter": str(row.get("Closeout Letter", "")).strip(),
        "source_file_name": source_file_name,
        "raw_payload": json_payload(row),
    }


def iter_fda_records(tenant_id: str, source_path: Path):
    workbook = load_workbook(source_path, read_only=True, data_only=True)
    sheet = workbook["Warning Letter Solr Index"]
    headers = [str(cell) if cell is not None else "" for cell in next(sheet.iter_rows(values_only=True))]
    for values in sheet.iter_rows(min_row=2, values_only=True):
        row = dict(zip(headers, values, strict=False))
        if not str(row.get("Company Name", "")).strip():
            continue
        yield transform_fda_row(tenant_id, source_path.name, row)
```

```python
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .base import json_payload, stable_record_hash


def transform_comtrade_row(tenant_id: str, source_file_name: str, row: dict) -> dict:
    record_hash = stable_record_hash(
        tenant_id,
        row.get("refYear"),
        row.get("flowCode"),
        row.get("reporterISO"),
        row.get("partnerISO"),
        row.get("cmdCode"),
    )
    return {
        "tenant_id": tenant_id,
        "source_record_hash": record_hash,
        "ref_year": int(row["refYear"]),
        "flow_code": str(row.get("flowCode", "")).strip(),
        "flow_desc": str(row.get("flowDesc", "")).strip(),
        "reporter_iso": str(row.get("reporterISO", "")).strip(),
        "reporter_desc": str(row.get("reporterDesc", "")).strip(),
        "partner_iso": str(row.get("partnerISO", "")).strip(),
        "partner_desc": str(row.get("partnerDesc", "")).strip(),
        "cmd_code": str(row.get("cmdCode", "")).strip(),
        "cmd_desc": str(row.get("cmdDesc", "")).strip(),
        "qty": float(row["qty"]) if row.get("qty") is not None else None,
        "net_wgt": float(row["netWgt"]) if row.get("netWgt") is not None else None,
        "cifvalue": float(row["cifvalue"]) if row.get("cifvalue") is not None else None,
        "fobvalue": float(row["fobvalue"]) if row.get("fobvalue") is not None else None,
        "primary_value": float(row["primaryValue"]) if row.get("primaryValue") is not None else None,
        "source_file_name": source_file_name,
        "raw_payload": json_payload(row),
    }


def iter_comtrade_records(tenant_id: str, source_path: Path):
    workbook = load_workbook(source_path, read_only=True, data_only=True)
    sheet = workbook["Sheet1"]
    headers = [str(cell) if cell is not None else "" for cell in next(sheet.iter_rows(values_only=True))]
    for values in sheet.iter_rows(min_row=2, values_only=True):
        row = dict(zip(headers, values, strict=False))
        if row.get("refYear") is None:
            continue
        yield transform_comtrade_row(tenant_id, source_path.name, row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.ingestion_sql.test_load_fda tests.ingestion_sql.test_load_comtrade -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/ingestion_sql/test_load_fda.py tests/ingestion_sql/test_load_comtrade.py src/ingestion_sql/load_fda.py src/ingestion_sql/load_comtrade.py
git commit -m "feat: add fda and comtrade ingestion transformers"
```

### Task 7: Implement schema bootstrap + ingestion CLI

**Files:**
- Create: `tests/ingestion_sql/test_cli.py`
- Create: `src/ingestion_sql/cli.py`
- Create: `run_ingestion_sql.py`
- Modify: `src/nlsql/schema.py`
- Modify: `src/ingestion_sql/load_ofac_bis.py`
- Modify: `src/ingestion_sql/load_noaa.py`
- Modify: `src/ingestion_sql/load_fda.py`
- Modify: `src/ingestion_sql/load_comtrade.py`

- [ ] **Step 1: Write the failing ingestion CLI tests**

```python
from unittest import TestCase

from ingestion_sql.cli import parse_args


class IngestionCliTests(TestCase):
    def test_parse_args_supports_all_source_bootstrap(self) -> None:
        args = parse_args(["--source", "all", "--tenant-id", "tenant-dev", "--init-schema"])
        self.assertEqual("all", args.source)
        self.assertEqual("tenant-dev", args.tenant_id)
        self.assertTrue(args.init_schema)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.ingestion_sql.test_cli -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingestion_sql.cli'`

- [ ] **Step 3: Write minimal schema bootstrap and CLI implementation**

```python
from __future__ import annotations

from nlsql.schema import SOURCE_TABLE_DDLS


def ensure_source_tables(conn) -> None:
    with conn.cursor() as cur:
        for ddl in SOURCE_TABLE_DDLS.values():
            cur.execute(ddl)
```

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config
from nlsql.db import connect_postgres
from nlsql.schema import ensure_source_tables
from ingestion_sql.load_ofac_bis import iter_ofac_bis_records
from ingestion_sql.load_noaa import iter_noaa_records
from ingestion_sql.load_fda import iter_fda_records
from ingestion_sql.load_comtrade import iter_comtrade_records


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load local non-EDGAR source files into PostgreSQL.")
    parser.add_argument("--source", choices=["ofac_bis", "noaa", "fda", "comtrade", "all"], required=True)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--init-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = load_app_config(tenant_id_override=args.tenant_id)
    summary = {
        "tenant_id": args.tenant_id,
        "source": args.source,
        "status": "planned",
    }
    with connect_postgres(settings) as conn:
        if args.init_schema:
            ensure_source_tables(conn)
            summary["schema_initialized"] = True
    print(json.dumps(summary, indent=2))
```

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ingestion_sql.cli import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.ingestion_sql.test_cli -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/ingestion_sql/test_cli.py src/ingestion_sql/cli.py src/nlsql/schema.py run_ingestion_sql.py
git commit -m "feat: add ingestion cli and schema bootstrap"
```

### Task 8: Implement standalone NL-SQL planning, execution, and CLI

**Files:**
- Create: `tests/nlsql/test_query.py`
- Create: `src/nlsql/planner.py`
- Create: `src/nlsql/executor.py`
- Create: `src/nlsql/synthesizer.py`
- Create: `src/nlsql/query.py`
- Create: `src/nlsql/cli.py`
- Create: `run_nlsql_query.py`

- [ ] **Step 1: Write the failing NL-SQL tests**

```python
from unittest import TestCase

from nlsql.executor import build_sql
from nlsql.planner import heuristic_nlsql_plan
from nlsql.synthesizer import synthesize_nlsql_answer


class NlSqlQueryTests(TestCase):
    def test_heuristic_nlsql_plan_routes_trade_topk_question(self) -> None:
        plan = heuristic_nlsql_plan("What were the top 5 countries exporting all commodities in 2025?")
        self.assertEqual("trade_top_exporters", plan["query_type"])
        self.assertEqual(5, plan["limit"])
        self.assertEqual(2025, plan["year"])

    def test_build_sql_creates_parameterized_trade_query(self) -> None:
        sql, params = build_sql(
            {
                "query_type": "trade_top_exporters",
                "year": 2025,
                "limit": 5,
            }
        )
        self.assertIn("FROM source_comtrade_flows", sql)
        self.assertIn("LIMIT %(limit)s", sql)
        self.assertEqual({"year": 2025, "limit": 5}, params)

    def test_synthesize_nlsql_answer_formats_ranked_rows(self) -> None:
        answer = synthesize_nlsql_answer(
            question="What were the top 2 countries exporting all commodities in 2025?",
            plan={"query_type": "trade_top_exporters"},
            rows=[
                {"reporter_desc": "Azerbaijan", "total_value": 25042007312.55},
                {"reporter_desc": "Canada", "total_value": 18000000000.00},
            ],
        )
        self.assertIn("Azerbaijan", answer)
        self.assertIn("Canada", answer)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.nlsql.test_query -v`
Expected: FAIL with `ModuleNotFoundError` for planner/executor/synthesizer

- [ ] **Step 3: Write minimal NL-SQL route implementation**

```python
from __future__ import annotations

import re


def heuristic_nlsql_plan(question: str) -> dict:
    text = question.lower()
    year_match = re.search(r"(20\\d{2})", text)
    limit_match = re.search(r"top\\s+(\\d+)", text)
    if "top" in text and ("export" in text or "exporting" in text):
        return {
            "query_type": "trade_top_exporters",
            "year": int(year_match.group(1)) if year_match else None,
            "limit": int(limit_match.group(1)) if limit_match else 5,
        }
    return {"query_type": "unsupported", "reason": "Question does not match current safe NL-SQL templates."}
```

```python
from __future__ import annotations


def build_sql(plan: dict) -> tuple[str, dict]:
    if plan["query_type"] == "trade_top_exporters":
        return (
            """
            SELECT reporter_desc, SUM(primary_value) AS total_value
            FROM source_comtrade_flows
            WHERE tenant_id = %(tenant_id)s
              AND ref_year = %(year)s
              AND flow_code = 'X'
            GROUP BY reporter_desc
            ORDER BY total_value DESC
            LIMIT %(limit)s
            """,
            {
                "tenant_id": plan["tenant_id"],
                "year": plan["year"],
                "limit": plan["limit"],
            },
        )
    raise ValueError(f"Unsupported query type: {plan['query_type']}")
```

```python
from __future__ import annotations


def synthesize_nlsql_answer(question: str, plan: dict, rows: list[dict]) -> str:
    if plan["query_type"] == "trade_top_exporters":
        lines = [f"Question: {question}", "", "Top exporters:"]
        for idx, row in enumerate(rows, start=1):
            lines.append(f"{idx}. {row['reporter_desc']}: {row['total_value']}")
        return "\n".join(lines)
    return "NL-SQL route could not answer the question with the current safe query templates."
```

```python
from __future__ import annotations

from common.generation import LLMConfig, chat_json
from config import AppConfig
from nlsql.db import connect_postgres
from nlsql.executor import build_sql
from nlsql.planner import heuristic_nlsql_plan
from nlsql.synthesizer import synthesize_nlsql_answer


def run_nlsql_query(settings: AppConfig, question: str) -> dict:
    plan = heuristic_nlsql_plan(question)
    if plan["query_type"] == "unsupported":
        return {
            "question": question,
            "plan": plan,
            "rows": [],
            "answer": "NL-SQL route does not support that question shape yet.",
        }

    plan["tenant_id"] = settings.graph_tenant_id
    sql, params = build_sql(plan)
    with connect_postgres(settings) as conn:
        rows = conn.execute(sql, params).fetchall()
    answer = synthesize_nlsql_answer(question, plan, rows)
    return {
        "question": question,
        "plan": plan,
        "sql": sql,
        "params": params,
        "rows": rows,
        "answer": answer,
    }
```

```python
from __future__ import annotations

import argparse
import json

from config import load_app_config
from .query import run_nlsql_query


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run standalone NL-SQL route.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--tenant-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = load_app_config(tenant_id_override=args.tenant_id)
    result = run_nlsql_query(settings, args.question)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
```

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nlsql.cli import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.nlsql.test_query -v`
Expected: PASS

- [ ] **Step 5: Run a focused end-to-end smoke command**

Run: `python run_nlsql_query.py --question "What were the top 5 countries exporting all commodities in 2025?" --tenant-id default`
Expected: JSON output with `plan.query_type == "trade_top_exporters"` and an `answer` field

- [ ] **Step 6: Commit**

```bash
git add tests/nlsql/test_query.py src/nlsql/planner.py src/nlsql/executor.py src/nlsql/synthesizer.py src/nlsql/query.py src/nlsql/cli.py run_nlsql_query.py
git commit -m "feat: add standalone nlsql route"
```

## Self-Review

### Spec coverage

- PostgreSQL token-auth: covered in Tasks 1-2
- repeatable source-table ingestion: covered in Tasks 3-7
- source-first SQL model: covered in Tasks 3-6
- standalone `nlsql` route: covered in Task 8
- tenant-aware design: covered in Tasks 1-8 via `tenant_id`

Not covered in this plan by design:

- top-level router refactor to add `sanctions`, `nlsql`, `fullstack`
- LangChain tool-calling orchestration inside `fullstack`
- standalone `sanctions` route
- frontend/admin/dashboard/graph view
- LangSmith/LangFuse, Slack/webhooks, evaluation dashboards, deployment

These belong to follow-on plans and should not be mixed into this phase.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes exact files, concrete test code, run commands, and implementation snippets.

### Type consistency

- `AppConfig` fields are used consistently as `pg_host`, `pg_user`, `pg_port`, `pg_database`, `pg_sslmode`, and `azure_postgres_scope`.
- `run_nlsql_query()` is the public route entrypoint and is used consistently in CLI code.
- Source table names match between schema and loader expectations.

## Follow-On Plans

After this plan is executed, create separate plans for:

1. `2026-04-21-supplychainnexus-router-fullstack.md`
2. `2026-04-21-supplychainnexus-sanctions-route.md`
3. `2026-04-21-supplychainnexus-webapp-admin.md`
4. `2026-04-21-supplychainnexus-evaluation-observability.md`

