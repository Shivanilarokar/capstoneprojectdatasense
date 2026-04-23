"""CLI for central LangGraph agentic router."""

from __future__ import annotations

import argparse
import json

from config import load_app_config

from .agent import AgenticOptions, run_agentic_query


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the LangGraph competition router across PageIndex, Sanctions, NL-SQL, GraphRAG, and fullstack."
    )
    parser.add_argument("--question", required=True, help="User question")
    parser.add_argument("--tenant-id", default=None, help="Tenant ID override")
    parser.add_argument("--user-id", default="system", help="User ID for auditing")
    parser.add_argument(
        "--force-pipeline",
        default="auto",
        choices=["auto", "pageindex", "sanctions", "nlsql", "graphrag", "fullstack"],
        help="Optional pipeline override. Default auto = smart routing.",
    )
    parser.add_argument(
        "--max-graph-results",
        type=int,
        default=20,
        help="Max rows per GraphRAG retrieval route.",
    )
    parser.add_argument(
        "--no-llm-synthesis",
        action="store_true",
        help="Disable LLM synthesis stages where possible.",
    )
    return parser.parse_args(argv)


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    settings = load_app_config(tenant_id_override=args.tenant_id)
    options = AgenticOptions(
        force_pipeline=None if args.force_pipeline == "auto" else args.force_pipeline,
        use_llm_synthesis=not args.no_llm_synthesis,
        graph_max_results=args.max_graph_results,
    )
    result = run_agentic_query(
        settings=settings,
        question=args.question,
        user_id=args.user_id,
        options=options,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
