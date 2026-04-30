from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from uuid import uuid4

from backend.app.control_plane.bootstrap import bootstrap_control_plane_database
from backend.app.control_plane.repository import ControlPlaneRepository


class ControlPlaneBootstrapTests(TestCase):
    def _database_url(self) -> str:
        database_path = Path("data") / f"test-control-plane-bootstrap-{uuid4().hex}.sqlite"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: database_path.unlink(missing_ok=True))
        return f"sqlite:///{database_path.resolve().as_posix()}"

    def test_bootstrap_control_plane_database_initializes_schema_without_seed_user(self) -> None:
        database_url = self._database_url()

        result = bootstrap_control_plane_database(database_url=database_url)

        repository = ControlPlaneRepository(database_url)
        self.assertEqual("ok", result["status"])
        self.assertFalse(repository.has_access_assignments())
        self.assertEqual(0, result["assignment_count"])

    def test_bootstrap_control_plane_database_can_seed_first_admin_assignment(self) -> None:
        database_url = self._database_url()

        result = bootstrap_control_plane_database(
            database_url=database_url,
            admin_email="founder@example.com",
            admin_display_name="Founder Admin",
            tenant_key="default",
            roles=("admin",),
        )

        repository = ControlPlaneRepository(database_url)
        access = repository.resolve_user_access("founder@example.com")

        self.assertEqual("ok", result["status"])
        self.assertIsNotNone(access)
        assert access is not None
        self.assertEqual("Founder Admin", access.display_name)
        self.assertEqual("default", access.tenant_key)
        self.assertEqual(("admin",), access.roles)
        self.assertTrue(access.is_default)
        self.assertEqual(1, result["assignment_count"])
