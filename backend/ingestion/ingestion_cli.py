from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from backend.config import load_app_config

from .base import batched, build_upsert_statement
from .load_comtrade import CONFLICT_COLUMNS as COMTRADE_CONFLICT_COLUMNS
from .load_comtrade import TABLE_NAME as COMTRADE_TABLE_NAME
from .load_comtrade import iter_comtrade_records
from .load_fda import CONFLICT_COLUMNS as FDA_CONFLICT_COLUMNS
from .load_fda import TABLE_NAME as FDA_TABLE_NAME
from .load_fda import iter_fda_records
from .load_noaa import CONFLICT_COLUMNS as NOAA_CONFLICT_COLUMNS
from .load_noaa import TABLE_NAME as NOAA_TABLE_NAME
from .load_noaa import iter_noaa_records
from .load_ofac_bis import CONFLICT_COLUMNS as OFAC_BIS_CONFLICT_COLUMNS
from .load_ofac_bis import TABLE_NAME as OFAC_BIS_TABLE_NAME
from .load_ofac_bis import iter_ofac_bis_records


@dataclass(frozen=True)
class SourceSpec:
    name: str
    table_name: str
    conflict_columns: tuple[str, ...]
    relative_path: Path
    iterator_factory: object
    legacy_relative_paths: tuple[Path, ...] = ()

    def resolve_path(self, project_root: Path) -> Path:
        candidate = (project_root / self.relative_path).resolve()
        if candidate.exists():
            return candidate

        for legacy_path in self.legacy_relative_paths:
            legacy_candidate = (project_root / legacy_path).resolve()
            if legacy_candidate.exists():
                return legacy_candidate

        parent = candidate.parent
        if parent.exists():
            same_extension = sorted(
                path for path in parent.iterdir() if path.is_file() and path.suffix == candidate.suffix
            )
            if len(same_extension) == 1:
                return same_extension[0].resolve()
        return candidate


SOURCE_SPECS = {
    "ofac_sdn": SourceSpec(
        name="ofac_sdn",
        table_name=OFAC_BIS_TABLE_NAME,
        conflict_columns=OFAC_BIS_CONFLICT_COLUMNS,
        relative_path=Path("data/ingestion/ofac_sdn/sdn_data.xlsx"),
        legacy_relative_paths=(Path("data/ingestion/ofac_bis/sdn_data.xlsx"),),
        iterator_factory=iter_ofac_bis_records,
    ),
    "noaa": SourceSpec(
        name="noaa",
        table_name=NOAA_TABLE_NAME,
        conflict_columns=NOAA_CONFLICT_COLUMNS,
        relative_path=Path("data/ingestion/noaa/StormEvents_details-ftp_v1.0_d2025_c20250717.csv"),
        iterator_factory=iter_noaa_records,
    ),
    "fda": SourceSpec(
        name="fda",
        table_name=FDA_TABLE_NAME,
        conflict_columns=FDA_CONFLICT_COLUMNS,
        relative_path=Path("data/ingestion/fda/warning-letters.xlsx"),
        iterator_factory=iter_fda_records,
    ),
    "comtrade": SourceSpec(
        name="comtrade",
        table_name=COMTRADE_TABLE_NAME,
        conflict_columns=COMTRADE_CONFLICT_COLUMNS,
        relative_path=Path("data/ingestion/comtrade/TradeData.xlsx"),
        iterator_factory=iter_comtrade_records,
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load local non-EDGAR source files into PostgreSQL.")
    parser.add_argument("--source", choices=["ofac_sdn", "ofac_bis", "noaa", "fda", "comtrade", "all"], required=True)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--init-schema", action="store_true")
    parser.add_argument("--reset-tables", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args(argv)


def selected_sources(source_name: str) -> list[SourceSpec]:
    if source_name == "ofac_bis":
        source_name = "ofac_sdn"
    if source_name == "all":
        return [SOURCE_SPECS[key] for key in ("ofac_sdn", "noaa", "fda", "comtrade")]
    return [SOURCE_SPECS[source_name]]


def load_records_into_table(
    conn,
    table_name: str,
    conflict_columns: list[str] | tuple[str, ...],
    records,
    *,
    batch_size: int = 1000,
) -> int:
    iterator = iter(records)
    first = next(iterator, None)
    if first is None:
        return 0

    columns = list(first.keys())
    sql = build_upsert_statement(table_name, columns, conflict_columns)
    total = 0
    with conn.cursor() as cur:
        for batch in batched(chain([first], iterator), size=batch_size):
            cur.executemany(sql, batch)
            total += len(batch)
    return total


def run_ingestion(
    *,
    source: str,
    tenant_id: str = "default",
    init_schema: bool = False,
    reset_tables: bool = False,
    batch_size: int = 1000,
) -> dict[str, object]:
    from backend.nlsql.db import connect_postgres
    from backend.nlsql.schema import drop_source_tables, ensure_source_tables

    settings = load_app_config(tenant_id_override=tenant_id)
    summary = {
        "tenant_id": settings.graph_tenant_id,
        "source": source,
        "schema_initialized": False,
        "schema_reset": False,
        "loaded": {},
    }

    with connect_postgres(settings) as conn:
        if reset_tables:
            drop_source_tables(conn)
            summary["schema_reset"] = True
            ensure_source_tables(conn)
            summary["schema_initialized"] = True
        elif init_schema:
            ensure_source_tables(conn)
            summary["schema_initialized"] = True

        for spec in selected_sources(source):
            source_path = spec.resolve_path(settings.project_root)
            loaded = load_records_into_table(
                conn=conn,
                table_name=spec.table_name,
                conflict_columns=spec.conflict_columns,
                records=spec.iterator_factory(settings.graph_tenant_id, source_path),
                batch_size=batch_size,
            )
            summary["loaded"][spec.name] = {
                "table_name": spec.table_name,
                "source_path": str(source_path),
                "row_count": loaded,
            }
    return summary


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        summary = run_ingestion(
            source=args.source,
            tenant_id=args.tenant_id,
            init_schema=args.init_schema,
            reset_tables=args.reset_tables,
            batch_size=args.batch_size,
        )
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        raise SystemExit(1) from exc

    print(json.dumps(summary, indent=2))


