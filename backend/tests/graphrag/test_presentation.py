from __future__ import annotations

from unittest import TestCase

from backend.graphrag.presentation import render_graph_output


class GraphPresentationTests(TestCase):
    def test_render_graph_output_renders_answer_first_sections(self) -> None:
        result = {
            "question": "Which suppliers are directly linked to sanctioned entities?",
            "routes": ["sanctions", "cascade"],
            "answer": "Two supplier-sanctions links were found in the graph.",
            "evidence": [
                {
                    "route": "sanctions",
                    "sanctions_list": [
                        {
                            "name": "ACME GLOBAL LTD",
                            "source_list": "sdn.xlsx",
                            "sanctions_type": "Entity",
                        }
                    ],
                    "exact_entity_matches": [
                        {
                            "supplier": "Acme Global Ltd",
                            "sanctioned_entity": "ACME GLOBAL LTD",
                            "match_type": "exact_primary",
                        }
                    ],
                },
                {
                    "route": "cascade",
                    "multi_tier_paths": [
                        {
                            "company": "Apple Inc.",
                            "tier1_supplier": "Hon Hai Precision Industry",
                            "tier2_supplier": "Acme Global Ltd",
                            "source_country": "Taiwan",
                            "sanctions_status": "matched",
                        }
                    ],
                    "topology_mode": "canonical",
                },
            ],
        }

        rendered = render_graph_output(result)

        self.assertIn("Question", rendered)
        self.assertIn("Answer", rendered)
        self.assertIn("Routes Used", rendered)
        self.assertIn("Evidence", rendered)
        self.assertIn("sanctions", rendered)
        self.assertIn("cascade", rendered)
        self.assertIn("Acme Global Ltd", rendered)
        self.assertIn("Apple Inc.", rendered)

    def test_render_graph_output_handles_empty_evidence(self) -> None:
        rendered = render_graph_output(
            {
                "question": "What hazards affect Taiwan?",
                "routes": [],
                "answer": "No graph evidence matched the query.",
                "evidence": [],
            }
        )

        self.assertIn("No retrieval routes were selected.", rendered)
        self.assertIn("No route evidence returned.", rendered)



