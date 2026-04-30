from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient
from jose import jwt

from backend.app.control_plane.repository import ControlPlaneRepository
from backend.main import app
from backend.tests.support.auth_tokens import issue_test_token


class AuthApiTests(TestCase):
    @patch.dict(
        "os.environ",
        {
            "APP_AUTH_SECRET": "test-app-auth-secret",
            "APP_AUTH_AUDIENCE": "supplychainnexus-api",
            "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
        },
        clear=False,
    )
    def test_auth_me_returns_signed_app_token_claims(self) -> None:
        client = TestClient(app)
        token = issue_test_token()

        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "subject": "user-1",
                "email": "user@example.com",
                "roles": ["user"],
                "tenant_key": "tenant-1",
            },
            response.json(),
        )

    def test_google_login_redirects_to_google_authorize_url(self) -> None:
        client = TestClient(app)

        with patch.dict(
            "os.environ",
            {
                "GOOGLE_CLIENT_ID": "google-client-id",
                "GOOGLE_CLIENT_SECRET": "google-client-secret",
                "GOOGLE_REDIRECT_URI": "http://127.0.0.1:8002/google/callback",
                "APP_AUTH_SECRET": "test-app-auth-secret",
                "APP_AUTH_AUDIENCE": "supplychainnexus-api",
                "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
            },
            clear=False,
        ):
            response = client.get("/google/login?return_to=/query", follow_redirects=False)

        self.assertEqual(302, response.status_code)
        location = response.headers["location"]
        parsed = urlparse(location)
        query = parse_qs(parsed.query)

        self.assertEqual("accounts.google.com", parsed.netloc)
        self.assertEqual("/o/oauth2/v2/auth", parsed.path)
        self.assertEqual(["google-client-id"], query["client_id"])
        self.assertEqual(["http://127.0.0.1:8002/google/callback"], query["redirect_uri"])
        self.assertEqual(["code"], query["response_type"])
        self.assertEqual(["openid email profile"], query["scope"])
        self.assertTrue(response.cookies.get("scn_google_oauth_state"))
        self.assertEqual("/query", response.cookies.get("scn_google_oauth_return_to", "").strip('"'))

    @patch("backend.app.api.auth.exchange_google_code_for_userinfo")
    def test_google_callback_redirects_back_to_frontend_with_access_token(self, exchange_userinfo: patch) -> None:
        exchange_userinfo.return_value = {
            "sub": "google-user-123",
            "email": "user@example.com",
            "name": "Google User",
        }
        client = TestClient(app)

        database_path = Path("data") / f"test-auth-control-plane-{uuid4().hex}.sqlite"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: database_path.unlink(missing_ok=True))
        database_url = f"sqlite:///{database_path.resolve().as_posix()}"
        repository = ControlPlaneRepository(database_url)
        repository.upsert_access_assignment(
            email="user@example.com",
            display_name="Google User",
            provider_subject="google-user-123",
            tenant_key="default",
            roles=("analyst",),
            status="active",
            is_default=True,
        )

        with patch.dict(
            "os.environ",
            {
                "GOOGLE_CLIENT_ID": "google-client-id",
                "GOOGLE_CLIENT_SECRET": "google-client-secret",
                "GOOGLE_REDIRECT_URI": "http://127.0.0.1:8002/google/callback",
                "GOOGLE_FRONTEND_REDIRECT_URI": "http://127.0.0.1:5173/auth/callback",
                "APP_AUTH_SECRET": "signing-secret",
                "APP_AUTH_AUDIENCE": "supplychainnexus-api",
                "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
                "CONTROL_PLANE_DATABASE_URL": database_url,
            },
            clear=False,
        ):
            client.cookies.set("scn_google_oauth_state", "expected-state")
            client.cookies.set("scn_google_oauth_return_to", "/query")
            response = client.get("/google/callback?code=sample-code&state=expected-state", follow_redirects=False)

        self.assertEqual(302, response.status_code)
        location = response.headers["location"]
        parsed = urlparse(location)
        query = parse_qs(parsed.query)

        self.assertEqual("127.0.0.1:5173", parsed.netloc)
        self.assertEqual("/auth/callback", parsed.path)
        self.assertEqual(["/query"], query["return_to"])

        access_token = query["access_token"][0]
        claims = jwt.get_unverified_claims(access_token)
        self.assertEqual("google-user-123", claims["sub"])
        self.assertEqual("user@example.com", claims["email"])
        self.assertEqual(["analyst"], claims["roles"])
        self.assertEqual("default", claims["tenant_key"])
        self.assertEqual("supplychainnexus-google-sso", claims["iss"])
        self.assertEqual("supplychainnexus-api", claims["aud"])

    @patch("backend.app.api.auth.exchange_google_code_for_userinfo")
    def test_google_callback_mints_roles_from_control_plane_assignments(self, exchange_userinfo: patch) -> None:
        exchange_userinfo.return_value = {
            "sub": "google-user-456",
            "email": "vp@example.com",
            "name": "Verified VP",
        }
        client = TestClient(app)

        database_path = Path("data") / f"test-auth-control-plane-{uuid4().hex}.sqlite"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: database_path.unlink(missing_ok=True))
        database_url = f"sqlite:///{database_path.resolve().as_posix()}"
        repository = ControlPlaneRepository(database_url)
        repository.upsert_access_assignment(
            email="vp@example.com",
            display_name="Verified VP",
            provider_subject="google-user-456",
            tenant_key="tenant-exec",
            roles=("vp",),
            status="active",
            is_default=True,
        )

        with patch.dict(
            "os.environ",
            {
                "GOOGLE_CLIENT_ID": "google-client-id",
                "GOOGLE_CLIENT_SECRET": "google-client-secret",
                "GOOGLE_REDIRECT_URI": "http://127.0.0.1:8002/google/callback",
                "GOOGLE_FRONTEND_REDIRECT_URI": "http://127.0.0.1:5173/auth/callback",
                "APP_AUTH_SECRET": "signing-secret",
                "APP_AUTH_AUDIENCE": "supplychainnexus-api",
                "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
                "CONTROL_PLANE_DATABASE_URL": database_url,
            },
            clear=False,
        ):
            client.cookies.set("scn_google_oauth_state", "expected-state")
            client.cookies.set("scn_google_oauth_return_to", "/query")
            response = client.get("/google/callback?code=sample-code&state=expected-state", follow_redirects=False)

        self.assertEqual(302, response.status_code)
        location = response.headers["location"]
        parsed = urlparse(location)
        query = parse_qs(parsed.query)

        access_token = query["access_token"][0]
        claims = jwt.get_unverified_claims(access_token)
        self.assertEqual(["vp"], claims["roles"])
        self.assertEqual("tenant-exec", claims["tenant_key"])

    @patch("backend.app.api.auth.exchange_google_code_for_userinfo")
    def test_google_callback_bootstraps_first_admin_when_control_plane_is_empty(self, exchange_userinfo: patch) -> None:
        exchange_userinfo.return_value = {
            "sub": "google-user-789",
            "email": "founder@example.com",
            "name": "Founding Admin",
        }
        client = TestClient(app)

        database_path = Path("data") / f"test-auth-control-plane-{uuid4().hex}.sqlite"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: database_path.unlink(missing_ok=True))
        database_url = f"sqlite:///{database_path.resolve().as_posix()}"

        with patch.dict(
            "os.environ",
            {
                "GOOGLE_CLIENT_ID": "google-client-id",
                "GOOGLE_CLIENT_SECRET": "google-client-secret",
                "GOOGLE_REDIRECT_URI": "http://127.0.0.1:8002/google/callback",
                "GOOGLE_FRONTEND_REDIRECT_URI": "http://127.0.0.1:5173/auth/callback",
                "APP_AUTH_SECRET": "signing-secret",
                "APP_AUTH_AUDIENCE": "supplychainnexus-api",
                "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
                "CONTROL_PLANE_DATABASE_URL": database_url,
                "GOOGLE_DEFAULT_TENANT_KEY": "default",
                "GOOGLE_ADMIN_EMAILS": "",
            },
            clear=False,
        ):
            client.cookies.set("scn_google_oauth_state", "expected-state")
            client.cookies.set("scn_google_oauth_return_to", "/admin")
            response = client.get("/google/callback?code=sample-code&state=expected-state", follow_redirects=False)

        self.assertEqual(302, response.status_code)
        location = response.headers["location"]
        query = parse_qs(urlparse(location).query)
        claims = jwt.get_unverified_claims(query["access_token"][0])

        self.assertEqual(["admin"], claims["roles"])
        self.assertEqual("default", claims["tenant_key"])
