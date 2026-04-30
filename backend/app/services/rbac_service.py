from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from backend.app.control_plane.db import get_control_plane_database_url
from backend.app.control_plane.repository import ControlPlaneRepository, UserAccessRecord
from backend.config import AppConfig, load_app_config


ROLE_CATALOG: tuple[str, ...] = ("admin", "analyst", "supplychain_manager", "vp")
WORKSPACE_ACCESS_ROLES: tuple[str, ...] = ROLE_CATALOG


def _repository(settings: AppConfig | None = None) -> ControlPlaneRepository:
    active_settings = settings or load_app_config()
    return ControlPlaneRepository(get_control_plane_database_url(active_settings))


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_role_values(roles: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for role in roles:
        value = str(role or "").strip()
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _validate_roles(roles: list[str]) -> tuple[str, ...]:
    normalized = _normalize_role_values(roles)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one role is required.")
    invalid = [role for role in normalized if role not in ROLE_CATALOG]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported roles requested: {', '.join(invalid)}",
        )
    return normalized


def resolve_google_identity_access(userinfo: dict[str, Any], settings: AppConfig | None = None) -> UserAccessRecord:
    active_settings = settings or load_app_config()
    repository = _repository(active_settings)
    email = _normalize_email(userinfo.get("email"))
    display_name = str(userinfo.get("name", "") or "").strip() or email
    provider_subject = str(userinfo.get("sub", "") or "").strip()

    access = repository.resolve_user_access(email)
    can_bootstrap_first_admin = not active_settings.google_admin_emails and not repository.has_access_assignments()
    if access is None and (email in active_settings.google_admin_emails or can_bootstrap_first_admin):
        access = repository.upsert_access_assignment(
            email=email,
            display_name=display_name,
            provider_subject=provider_subject,
            tenant_key=active_settings.google_default_tenant_key or "default",
            roles=("admin",),
            status="active",
            is_default=True,
        )

    if access is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has not been provisioned with workspace access.",
        )

    repository.touch_user_identity(
        email=email,
        display_name=display_name,
        provider_subject=provider_subject,
    )
    access = repository.resolve_user_access(email, tenant_key=access.tenant_key) or access

    if access.status.lower() != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User access is not active for this tenant.",
        )
    if not access.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no roles assigned for this tenant.",
        )

    return access


def build_admin_overview(settings: AppConfig | None = None) -> dict[str, object]:
    active_settings = settings or load_app_config()
    repository = _repository(active_settings)
    users = repository.list_access_assignments()
    tenants = repository.list_tenant_access_summaries()
    unique_emails = {user.email for user in users}
    admin_emails = {user.email for user in users if "admin" in user.roles}

    return {
        "status": "ok",
        "cards": [
            {"label": "Users", "value": str(len(unique_emails))},
            {"label": "Admins", "value": str(len(admin_emails))},
            {"label": "Tenants", "value": str(len(tenants))},
            {"label": "Assignments", "value": str(len(users))},
        ],
        "tenants": [tenant.to_dict() for tenant in tenants],
        "users": [user.to_dict() for user in users],
        "available_roles": list(ROLE_CATALOG),
    }


def upsert_workspace_access(
    *,
    email: str,
    display_name: str,
    tenant_key: str,
    roles: list[str],
    status_value: str,
    is_default: bool,
    settings: AppConfig | None = None,
) -> dict[str, object]:
    active_settings = settings or load_app_config()
    repository = _repository(active_settings)
    normalized_email = _normalize_email(email)
    normalized_roles = _validate_roles(roles)
    record = repository.upsert_access_assignment(
        email=normalized_email,
        display_name=display_name,
        provider_subject="",
        tenant_key=tenant_key.strip() or active_settings.google_default_tenant_key or "default",
        roles=normalized_roles,
        status=status_value.strip() or "active",
        is_default=is_default,
    )
    return record.to_dict()
