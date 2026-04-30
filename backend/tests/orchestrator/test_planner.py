from __future__ import annotations

from unittest import TestCase

from backend.orchestrator.planner import plan_query


class OrchestratorPlannerTests(TestCase):
    def test_plan_query_keeps_single_route_questions_as_single(self) -> None:
        plan = plan_query("Which states had the highest storm damage?")

        self.assertEqual("single", plan["plan_type"])
        self.assertEqual("nlsql", plan["pipeline"])
        self.assertEqual(["nlsql"], plan["routes"])
        self.assertEqual(1, len(plan["subquestions"]))

    def test_plan_query_decomposes_cross_source_questions(self) -> None:
        plan = plan_query(
            "Is Acme Global sanctioned, what FDA warning letters mention it, and what cascade risk follows downstream?"
        )

        self.assertEqual("multi", plan["plan_type"])
        self.assertEqual("fullstack", plan["pipeline"])
        self.assertEqual("tier_2", plan["tier_hint"])
        self.assertEqual(["sanctions", "nlsql", "graphrag"], plan["routes"])
        self.assertGreaterEqual(len(plan["subquestions"]), 2)
