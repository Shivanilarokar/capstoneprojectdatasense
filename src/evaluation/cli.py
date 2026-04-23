from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_app_config

from .runner import run_benchmarks


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SupplyChainNexus competition benchmark.")
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-file", default=None, help="Optional JSON file for saving benchmark results.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = load_app_config(tenant_id_override=args.tenant_id)
    report = run_benchmarks(settings, limit=args.limit)
    if args.output_file:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
