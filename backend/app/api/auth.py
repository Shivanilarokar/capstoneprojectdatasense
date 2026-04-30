from __future__ import annotations

import secrets
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from jose import jwt

from backend.app.api.deps import get_current_principal
from backend.app.api.models.auth import CurrentPrincipalResponse
from backend.app.auth.principal import CurrentPrincipal
from backend.app.services.rbac_service import resolve_google_identity_access
from backend.config import AppConfig, load_app_config


router = APIRouter(tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_STATE_COOKIE = "scn_google_oauth_state"
GOOGLE_RETURN_TO_COOKIE = "scn_google_oauth_return_to"
GOOGLE_COOKIE_MAX_AGE_SECONDS = 600
GOOGLE_TOKEN_LIFETIME_SECONDS = 3600


def _sanitize_return_to(return_to: str | None) -> str:
    normalized = str(return_to or "").strip()
    if not normalized.startswith("/") or normalized.startswith("//"):
        return "/"
    return normalized


def _append_query_params(url: str, **params: str) -> str:
    split = urlsplit(url)
    merged = dict(parse_qsl(split.query, keep_blank_values=True))
    merged.update(params)
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(merged), split.fragment))


def _require_google_settings(settings: AppConfig) -> AppConfig:
    if settings.google_client_id and settings.google_client_secret and settings.app_auth_secret:
        return settings

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Google OAuth or application JWT signing is not configured in the environment.",
    )


def _app_auth_secret(settings: AppConfig) -> str:
    secret = settings.app_auth_secret.strip()
    if secret:
        return secret

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Application JWT signing secret is not configured.",
    )


def _build_google_authorize_url(settings: AppConfig, state_token: str) -> str:
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": settings.google_scope or "openid email profile",
            "access_type": "online",
            "include_granted_scopes": "true",
            "prompt": "select_account",
            "state": state_token,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_google_code_for_userinfo(code: str, settings: AppConfig) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            token_response.raise_for_status()
            token_data = token_response.json()

            access_token = str(token_data.get("access_token", "") or "").strip()
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Google token exchange did not return an access token.",
                )

            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google sign-in failed during token exchange.",
        ) from exc

    userinfo = userinfo_response.json()
    if not str(userinfo.get("sub", "") or "").strip() or not str(userinfo.get("email", "") or "").strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google user profile is missing required subject or email fields.",
        )
    if userinfo.get("email_verified") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google account email must be verified.",
        )

    return userinfo


def _create_google_access_token(userinfo: dict[str, Any], settings: AppConfig) -> str:
    now = int(time.time())
    access = resolve_google_identity_access(userinfo, settings)
    claims: dict[str, Any] = {
        "sub": str(userinfo["sub"]).strip(),
        "email": str(userinfo["email"]).strip(),
        "name": str(userinfo.get("name", "") or "").strip(),
        "roles": list(access.roles),
        "tenant_key": access.tenant_key,
        "provider": "google",
        "iat": now,
        "exp": now + GOOGLE_TOKEN_LIFETIME_SECONDS,
        "iss": settings.app_auth_issuer,
        "aud": settings.app_auth_audience,
    }
    return jwt.encode(claims, _app_auth_secret(settings), algorithm="HS256")


def _build_frontend_callback_url(
    settings: AppConfig,
    *,
    return_to: str,
    access_token: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> str:
    query: dict[str, str] = {"return_to": _sanitize_return_to(return_to)}
    if access_token:
        query["access_token"] = access_token
    if error:
        query["error"] = error
    if error_description:
        query["error_description"] = error_description
    return _append_query_params(settings.google_frontend_redirect_uri, **query)


@router.get("/auth/me", response_model=CurrentPrincipalResponse)
def current_user(principal: CurrentPrincipal = Depends(get_current_principal)) -> CurrentPrincipalResponse:
    return CurrentPrincipalResponse(
        subject=principal.subject,
        email=principal.email,
        roles=list(principal.roles),
        tenant_key=principal.tenant_key,
    )




@router.get("/google/login")
def google_login(return_to: str = Query("/query")) -> RedirectResponse:
    settings = _require_google_settings(load_app_config())
    state_token = secrets.token_urlsafe(32)
    sanitized_return_to = _sanitize_return_to(return_to)
    response = RedirectResponse(
        url=_build_google_authorize_url(settings, state_token),
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        GOOGLE_STATE_COOKIE,
        state_token,
        httponly=True,
        max_age=GOOGLE_COOKIE_MAX_AGE_SECONDS,
        samesite="lax",
    )
    response.set_cookie(
        GOOGLE_RETURN_TO_COOKIE,
        sanitized_return_to,
        httponly=True,
        max_age=GOOGLE_COOKIE_MAX_AGE_SECONDS,
        samesite="lax",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    settings = _require_google_settings(load_app_config())
    return_to = _sanitize_return_to(request.cookies.get(GOOGLE_RETURN_TO_COOKIE, "/query"))
    expected_state = str(request.cookies.get(GOOGLE_STATE_COOKIE, "") or "").strip()

    if error:
        response = RedirectResponse(
            url=_build_frontend_callback_url(
                settings,
                return_to=return_to,
                error=error,
                error_description=error_description,
            ),
            status_code=status.HTTP_302_FOUND,
        )
        response.delete_cookie(GOOGLE_STATE_COOKIE)
        response.delete_cookie(GOOGLE_RETURN_TO_COOKIE)
        return response

    if not code or not state or not expected_state or state != expected_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google sign-in state mismatch.")

    try:
        userinfo = await exchange_google_code_for_userinfo(code, settings)
        access_token = _create_google_access_token(userinfo, settings)
    except HTTPException as exc:
        response = RedirectResponse(
            url=_build_frontend_callback_url(
                settings,
                return_to=return_to,
                error="access_denied" if exc.status_code == status.HTTP_403_FORBIDDEN else "oauth_error",
                error_description=str(exc.detail),
            ),
            status_code=status.HTTP_302_FOUND,
        )
        response.delete_cookie(GOOGLE_STATE_COOKIE)
        response.delete_cookie(GOOGLE_RETURN_TO_COOKIE)
        return response

    response = RedirectResponse(
        url=_build_frontend_callback_url(settings, return_to=return_to, access_token=access_token),
        status_code=status.HTTP_302_FOUND,
    )
    response.delete_cookie(GOOGLE_STATE_COOKIE)
    response.delete_cookie(GOOGLE_RETURN_TO_COOKIE)
    return response
