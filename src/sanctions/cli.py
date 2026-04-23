from __future__ import annotations

import argparse
import json

from config import load_app_config

from .query import run_sanctions_query


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic sanctions screening.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--user-id", default="system")
    parser.add_argument(
        "--entity",
        action="append",
        dest="entities",
        default=None,
        help="Optional entity override. Repeat for multiple entities.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = load_app_config(tenant_id_override=args.tenant_id)
    result = run_sanctions_query(
        settings,
        args.question,
        entity_names=args.entities,
        user_id=args.user_id,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
