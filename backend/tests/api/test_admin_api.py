from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from unittest import TestCase
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.control_plane.repository import ControlPlaneRepository
from backend.tests.support.auth_tokens import issue_test_token


class AdminApiTests(TestCase):
    @patch.dict(
        "os.environ",
        {
            "APP_AUTH_SECRET": "test-app-auth-secret",
            "APP_AUTH_AUDIENCE": "supplychainnexus-api",
            "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
        },
        clear=False,
    )
    def test_admin_overview_requires_admin_role(self) -> None:
        client = TestClient(app)
        denied_token = issue_test_token(roles=("user",))
        allowed_token = issue_test_token(roles=("user", "admin"))

        denied = client.get(
            "/admin/overview",
            headers={"Authorization": f"Bearer {denied_token}"},
        )
        allowed = client.get(
            "/admin/overview",
            headers={"Authorization": f"Bearer {allowed_token}"},
        )

        self.assertEqual(403, denied.status_code)
        self.assertEqual(200, allowed.status_code)
        self.assertEqual("ok", allowed.json()["status"])

    @patch.dict(
        "os.environ",
        {
            "APP_AUTH_SECRET": "test-app-auth-secret",
            "APP_AUTH_AUDIENCE": "supplychainnexus-api",
            "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
        },
        clear=False,
    )
    def test_admin_can_manage_role_assignments(self) -> None:
        database_path = Path("data") / f"test-admin-control-plane-{uuid4().hex}.sqlite"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: database_path.unlink(missing_ok=True))
        database_url = f"sqlite:///{database_path.resolve().as_posix()}"
        with patch.dict("os.environ", {"CONTROL_PLANE_DATABASE_URL": database_url}, clear=False):
            repository = ControlPlaneRepository(database_url)
            repository.upsert_access_assignment(
                email="admin@example.com",
                display_name="Admin User",
                provider_subject="google-admin-1",
                tenant_key="tenant-acme",
                roles=("admin",),
                status="active",
                is_default=True,
            )
            client = TestClient(app)
            allowed_token = issue_test_token(roles=("admin",), tenant_key="tenant-acme", email="admin@example.com")

            update = client.put(
                "/admin/access/analyst.user%40example.com",
                json={
                    "display_name": "Analyst User",
                    "tenant_key": "tenant-acme",
                    "roles": ["analyst", "supplychain_manager"],
                    "status": "active",
                    "is_default": True,
                },
                headers={"Authorization": f"Bearer {allowed_token}"},
            )
            overview = client.get(
                "/admin/overview",
                headers={"Authorization": f"Bearer {allowed_token}"},
            )

        self.assertEqual(200, update.status_code)
        self.assertEqual("active", update.json()["status"])
        self.assertEqual(200, overview.status_code)
        self.assertEqual(
            ["admin", "analyst", "supplychain_manager", "vp"],
            overview.json()["available_roles"],
        )
        self.assertTrue(
            any(
                user["email"] == "analyst.user@example.com"
                and user["tenant_key"] == "tenant-acme"
                and user["roles"] == ["analyst", "supplychain_manager"]
                for user in overview.json()["users"]
            )
        )
