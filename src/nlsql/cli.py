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
