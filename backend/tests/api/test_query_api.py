from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.support.auth_tokens import issue_test_token


class QueryApiTests(TestCase):
    @patch("backend.app.api.query.ask_supplychainnexus")
    @patch.dict(
        "os.environ",
        {
            "APP_AUTH_SECRET": "test-app-auth-secret",
            "APP_AUTH_AUDIENCE": "supplychainnexus-api",
            "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
        },
        clear=False,
    )
    def test_query_endpoint_exists(self, ask_mock) -> None:
        ask_mock.return_value = {
            "status": "ok",
            "question": "Which states had the highest storm damage?",
            "answer": "Illinois had the highest damage.",
            "selected_pipeline": "nlsql",
            "route_plan": {"pipeline": "nlsql", "routes": ["nlsql"]},
            "warnings": [],
            "query_id": "query-1",
            "routes_executed": ["nlsql"],
        }
        client = TestClient(app)
        token = issue_test_token(roles=("analyst",))

        response = client.post(
            "/query/ask",
            json={"question": "Which states had the highest storm damage?"},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("nlsql", response.json()["selected_pipeline"])

    @patch("backend.app.api.query.ask_supplychainnexus")
    @patch.dict(
        "os.environ",
        {
            "APP_AUTH_SECRET": "test-app-auth-secret",
            "APP_AUTH_AUDIENCE": "supplychainnexus-api",
            "APP_AUTH_ISSUER": "supplychainnexus-google-sso",
        },
        clear=False,
    )
    def test_query_endpoint_requires_workspace_role(self, ask_mock) -> None:
        client = TestClient(app)
        token = issue_test_token(roles=("user",))

        response = client.post(
            "/query/ask",
            json={"question": "Which states had the highest storm damage?"},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(403, response.status_code)
        ask_mock.assert_not_called()
