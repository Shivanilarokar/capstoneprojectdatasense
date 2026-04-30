from __future__ import annotations
from typing import Any

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

from backend.app.auth.principal import CurrentPrincipal
from backend.config import AppConfig, load_app_config


def _normalize_roles(raw_roles: Any) -> tuple[str, ...]:
    if isinstance(raw_roles, str):
        return (raw_roles,) if raw_roles.strip() else ()
    if isinstance(raw_roles, list):
        roles: list[str] = []
        for value in raw_roles:
            role = str(value or "").strip()
            if role and role not in roles:
                roles.append(role)
        return tuple(roles)
    return ()


def _resolve_tenant_key(claims: dict[str, Any]) -> str:
    for key in ("tenant_key", "organization", "org_id", "tid"):
        value = str(claims.get(key, "") or "").strip()
        if value:
            return value
    return "default"


def _resolve_email(claims: dict[str, Any]) -> str:
    for key in ("email", "preferred_username", "upn"):
        value = str(claims.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _validate_claims(claims: dict[str, Any], settings: AppConfig) -> CurrentPrincipal:
    subject = str(claims.get("sub", "") or "").strip()
    email = _resolve_email(claims)
    roles = _normalize_roles(claims.get("roles", ()))
    tenant_key = _resolve_tenant_key(claims)

    if not subject or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required subject or email claims.",
        )

    return CurrentPrincipal(
        subject=subject,
        email=email,
        roles=roles,
        tenant_key=tenant_key,
        token_claims=claims,
    )


def _app_signing_secret(settings: AppConfig) -> str:
    secret = settings.app_auth_secret.strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Application JWT signing secret is not configured.",
        )
    return secret


def validate_access_token(token: str, settings: AppConfig | None = None) -> CurrentPrincipal:
    """Validate the signed application JWT and map it into the current-principal shape."""

    active_settings = settings or load_app_config()
    normalized_token = token.strip()
    if normalized_token.lower().startswith("bearer "):
        normalized_token = normalized_token.split(None, 1)[1].strip()

    try:
        claims = jwt.decode(
            normalized_token,
            _app_signing_secret(active_settings),
            algorithms=["HS256"],
            audience=active_settings.app_auth_audience,
            issuer=active_settings.app_auth_issuer,
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token has expired.",
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is invalid.",
        ) from exc

    return _validate_claims(claims, active_settings)
