from __future__ import annotations

from unittest import TestCase

from backend.orchestrator.state import GraphState, OrchestratorState


class OrchestratorStateTests(TestCase):
    def test_graph_state_exports_orchestrator_alias(self) -> None:
        self.assertIs(GraphState, OrchestratorState)
