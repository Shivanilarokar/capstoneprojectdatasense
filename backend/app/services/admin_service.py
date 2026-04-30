from __future__ import annotations

from backend.app.services.rbac_service import build_admin_overview, upsert_workspace_access
from backend.config import AppConfig, load_app_config


def build_admin_overview_snapshot(settings: AppConfig | None = None) -> dict[str, object]:
    return build_admin_overview(settings or load_app_config())


def save_admin_access_assignment(
    *,
    email: str,
    display_name: str,
    tenant_key: str,
    roles: list[str],
    status_value: str,
    is_default: bool,
    settings: AppConfig | None = None,
) -> dict[str, object]:
    return upsert_workspace_access(
        email=email,
        display_name=display_name,
        tenant_key=tenant_key,
        roles=roles,
        status_value=status_value,
        is_default=is_default,
        settings=settings or load_app_config(),
    )
