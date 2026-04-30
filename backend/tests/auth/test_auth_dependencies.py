from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException
from jose import jwt

from backend.app.auth.jwt_auth import validate_access_token
from backend.app.auth.principal import CurrentPrincipal


class AuthDependencyTests(TestCase):
    def test_principal_role_check(self) -> None:
        principal = CurrentPrincipal(
            subject="user-1",
            email="user@example.com",
            roles=("user",),
            tenant_key="tenant-1",
            token_claims={},
        )

        self.assertTrue(principal.has_role("user"))
        self.assertFalse(principal.has_role("admin"))

    @patch.dict(
        os.environ,
        {
            "APP_AUTH_SECRET": "expected-signing-secret",
            "APP_AUTH_AUDIENCE": "supplychainnexus-api",
            "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
        },
        clear=False,
    )
    def test_google_issued_token_requires_valid_signature(self) -> None:
        token = jwt.encode(
            {
                "sub": "user-1",
                "email": "user@example.com",
                "roles": ["user"],
                "tenant_key": "tenant-1",
                "iss": "supplychainnexus-google-sso",
                "aud": "supplychainnexus-api",
            },
            "wrong-signing-secret",
            algorithm="HS256",
        )

        with self.assertRaises(HTTPException) as caught:
            validate_access_token(token)

        self.assertEqual(401, caught.exception.status_code)

    def test_dev_token_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            validate_access_token("dev-user")

        self.assertEqual(401, caught.exception.status_code)
