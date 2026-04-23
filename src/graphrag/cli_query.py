"""CLI for Graph RAG query."""

from __future__ import annotations

import argparse
import json

from config import load_app_config
from .query import run_graph_query


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query SupplyChainNexus Graph RAG.")
    parser.add_argument("--question", required=True, help="User question")
    parser.add_argument("--tenant-id", default=None, help="Tenant ID for graph isolation")
    parser.add_argument("--max-results", type=int, default=20, help="Max rows per retrieval route")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM synthesis")
    parser.add_argument("--user-id", default="system", help="User ID for sanctions audit log")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_app_config(tenant_id_override=args.tenant_id)
    result = run_graph_query(
        settings=settings,
        question=args.question,
        max_results=args.max_results,
        use_llm_synthesis=not args.no_llm,
        user_id=args.user_id,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
