from __future__ import annotations

import argparse
import json
import os
from typing import Any

from backend.app.control_plane.repository import ControlPlaneRepository


def _normalize_roles(raw_roles: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    values = raw_roles or ("admin",)
    normalized: list[str] = []
    for value in values:
        role = str(value or "").strip()
        if role and role not in normalized:
            normalized.append(role)
    return tuple(normalized or ("admin",))


def bootstrap_control_plane_database(
    *,
    database_url: str,
    admin_email: str | None = None,
    admin_display_name: str | None = None,
    provider_subject: str = "",
    tenant_key: str = "default",
    roles: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    normalized_database_url = str(database_url or "").strip()
    if not normalized_database_url:
        raise ValueError("database_url is required for control-plane bootstrap.")

    repository = ControlPlaneRepository(normalized_database_url)
    repository.ensure_schema()

    seeded_email = str(admin_email or "").strip().lower()
    if seeded_email:
        repository.upsert_access_assignment(
            email=seeded_email,
            display_name=str(admin_display_name or "").strip() or seeded_email,
            provider_subject=str(provider_subject or "").strip(),
            tenant_key=str(tenant_key or "").strip() or "default",
            roles=_normalize_roles(roles),
            status="active",
            is_default=True,
        )

    assignments = repository.list_access_assignments()
    return {
        "status": "ok",
        "database_backend": "sqlite" if normalized_database_url.startswith("sqlite:///") else "postgresql",
        "seeded_admin_email": seeded_email or None,
        "assignment_count": len(assignments),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize the SupplyChainNexus control-plane database.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("CONTROL_PLANE_DATABASE_URL", "").strip(),
        help="Target control-plane database URL. Defaults to CONTROL_PLANE_DATABASE_URL.",
    )
    parser.add_argument("--seed-admin-email", default="", help="Optional first admin email to seed.")
    parser.add_argument("--seed-admin-name", default="", help="Display name for the seeded admin.")
    parser.add_argument("--provider-subject", default="", help="Optional Google subject for the seeded admin.")
    parser.add_argument("--tenant-key", default="default", help="Tenant key for the seeded admin assignment.")
    parser.add_argument(
        "--role",
        action="append",
        dest="roles",
        default=[],
        help="Role to assign to the seeded admin. Repeat for multiple roles. Defaults to admin.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = bootstrap_control_plane_database(
        database_url=args.database_url,
        admin_email=args.seed_admin_email,
        admin_display_name=args.seed_admin_name,
        provider_subject=args.provider_subject,
        tenant_key=args.tenant_key,
        roles=tuple(args.roles),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
