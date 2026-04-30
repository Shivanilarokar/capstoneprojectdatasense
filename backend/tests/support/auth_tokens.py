from __future__ import annotations

import time
from typing import Iterable

from jose import jwt


def issue_test_token(
    *,
    secret: str = "test-app-auth-secret",
    subject: str = "user-1",
    email: str = "user@example.com",
    roles: Iterable[str] = ("user",),
    tenant_key: str = "tenant-1",
    audience: str = "supplychainnexus-api",
    issuer: str = "supplychainnexus-google-sso",
    lifetime_seconds: int = 3600,
) -> str:
    now = int(time.time())
    claims = {
        "sub": subject,
        "email": email,
        "roles": list(roles),
        "tenant_key": tenant_key,
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + lifetime_seconds,
    }
    return jwt.encode(claims, secret, algorithm="HS256")
