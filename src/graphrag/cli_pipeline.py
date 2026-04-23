"""CLI for syncing structured sources into the GraphRAG Neo4j state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config

from .pipeline import sync_graph_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync PostgreSQL source tables and SEC sections into Neo4j GraphRAG state.")
    parser.add_argument("--tenant-id", default=None, help="Tenant ID override")
    parser.add_argument(
        "--sections-json",
        default="data/ingestion/sec/extracted_10k_sections.json",
        help="SEC extracted sections JSON input",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_app_config(tenant_id_override=args.tenant_id)
    summary = sync_graph_state(settings, sections_json_path=Path(args.sections_json))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
