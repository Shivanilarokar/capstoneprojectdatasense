from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.auth.jwt_auth import validate_access_token
from backend.app.auth.principal import CurrentPrincipal
from backend.app.services.rbac_service import WORKSPACE_ACCESS_ROLES
from backend.app.tenancy.resolver import resolve_tenant_runtime
from backend.config import AppConfig, load_app_config


bearer_scheme = HTTPBearer(auto_error=True)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentPrincipal:
    return validate_access_token(credentials.credentials)


def require_any_role(*roles: str):
    allowed = tuple(dict.fromkeys(role.strip() for role in roles if role.strip()))

    def dependency(principal: CurrentPrincipal = Depends(get_current_principal)) -> CurrentPrincipal:
        if not principal.has_any_role(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of the following roles is required: {', '.join(allowed)}",
            )
        return principal

    return dependency


def require_workspace_access(principal: CurrentPrincipal = Depends(require_any_role(*WORKSPACE_ACCESS_ROLES))) -> CurrentPrincipal:
    return principal


def require_admin(principal: CurrentPrincipal = Depends(require_any_role("admin"))) -> CurrentPrincipal:
    return principal


def get_current_settings(principal: CurrentPrincipal = Depends(get_current_principal)) -> AppConfig:
    settings = load_app_config(tenant_id_override=principal.tenant_key)
    context = resolve_tenant_runtime(principal.tenant_key, settings)
    return settings.with_tenant(context.tenant_key)
