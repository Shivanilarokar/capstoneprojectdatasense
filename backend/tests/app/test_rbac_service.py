from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from uuid import uuid4

from backend.app.control_plane.repository import ControlPlaneRepository


class ControlPlaneRbacRepositoryTests(TestCase):
    def test_upsert_and_resolve_user_session_returns_default_tenant_roles(self) -> None:
        database_path = Path("data") / f"test-control-plane-{uuid4().hex}.sqlite"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: database_path.unlink(missing_ok=True))
        database_url = f"sqlite:///{database_path.resolve().as_posix()}"
        repository = ControlPlaneRepository(database_url)

        repository.upsert_access_assignment(
            email="analyst@example.com",
            display_name="Ada Analyst",
            provider_subject="google-subject-1",
            tenant_key="tenant-acme",
            roles=("analyst", "vp"),
            status="active",
            is_default=True,
        )

        access = repository.resolve_user_access("analyst@example.com")

        self.assertIsNotNone(access)
        assert access is not None
        self.assertEqual("analyst@example.com", access.email)
        self.assertEqual("Ada Analyst", access.display_name)
        self.assertEqual("tenant-acme", access.tenant_key)
        self.assertEqual(("analyst", "vp"), access.roles)
        self.assertEqual("google-subject-1", access.provider_subject)
