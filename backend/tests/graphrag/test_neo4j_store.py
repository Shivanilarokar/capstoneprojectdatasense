from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from neo4j.exceptions import AuthError

from backend.config import load_app_config
from backend.graphrag.neo4j_store import Neo4jStore


class _FakeDriver:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.closed = False

    def verify_connectivity(self):
        if self.error is not None:
            raise self.error

    def close(self):
        self.closed = True


class Neo4jStoreTests(TestCase):
    def test_auth_error_is_reported_cleanly(self) -> None:
        settings = load_app_config()
        fake_driver = _FakeDriver(AuthError("bad credentials"))

        with patch("backend.graphrag.neo4j_store.GraphDatabase.driver", return_value=fake_driver):
            with self.assertRaisesRegex(RuntimeError, "Neo4j authentication failed"):
                Neo4jStore(settings)

        self.assertTrue(fake_driver.closed)




