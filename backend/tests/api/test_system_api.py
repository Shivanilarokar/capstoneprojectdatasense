from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class SystemApiTests(TestCase):
    def test_health_endpoint(self) -> None:
        client = TestClient(app)

        response = client.get("/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    @patch.dict(
        os.environ,
        {
            "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
        },
        clear=False,
    )
    def test_auth_preflight_allows_frontend_origin_and_authorization_header(self) -> None:
        client = TestClient(app)

        response = client.options(
            "/auth/me",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("http://127.0.0.1:5173", response.headers["access-control-allow-origin"])
        self.assertEqual("true", response.headers["access-control-allow-credentials"])
        self.assertIn("Authorization", response.headers["access-control-allow-headers"])
