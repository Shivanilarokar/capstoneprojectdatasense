from __future__ import annotations

from pathlib import Path
from unittest import TestCase


class NoCliSurfaceTests(TestCase):
    def test_legacy_run_wrappers_are_removed(self) -> None:
        root = Path(__file__).resolve().parents[2]

        self.assertFalse((root / "run_agentic_router.py").exists())
        self.assertFalse((root / "run_graphrag_query.py").exists())
        self.assertFalse((root / "run_nlsql_query.py").exists())
