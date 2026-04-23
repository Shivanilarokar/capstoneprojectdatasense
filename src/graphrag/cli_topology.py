"""CLI for building canonical multi-tier supply chain topology."""

from __future__ import annotations

import argparse
import json

from config import load_app_config

from .topology import build_multi_tier_topology


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build canonical multi-tier graph topology for SupplyChainNexus Graph RAG."
    )
    parser.add_argument("--tenant-id", default=None, help="Tenant ID override")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_app_config(tenant_id_override=args.tenant_id)
    summary = build_multi_tier_topology(settings)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

