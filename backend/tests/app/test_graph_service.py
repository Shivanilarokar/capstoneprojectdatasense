from __future__ import annotations

from unittest import TestCase

from backend.app.services.graph_service import build_answer_graph


class GraphServiceTests(TestCase):
    def test_build_answer_graph_creates_supply_chain_elements_from_cascade_evidence(self) -> None:
        result = {
            "query_id": "query-123",
            "route_results": {
                "graphrag": {
                    "evidence": {
                        "results": [
                            {
                                "route": "cascade",
                                "multi_tier_paths": [
                                    {
                                        "company": "ACME",
                                        "ticker": "ACM",
                                        "tier1_supplier": "Tier1 Metals",
                                        "tier2_supplier": "Tier2 Smelting",
                                        "component": "Battery Pack",
                                        "raw_material": "Lithium",
                                        "source_country": "Chile",
                                        "hazard_zone": "Atacama:Antofagasta",
                                        "sanctions_status": "clear",
                                        "sanctions_match_type": "none",
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        }

        graph = build_answer_graph(result)

        self.assertEqual("answer", graph["mode"])
        self.assertEqual("query-123", graph["query_id"])
        self.assertGreaterEqual(len(graph["nodes"]), 6)
        self.assertGreaterEqual(len(graph["edges"]), 5)
        labels = {node["data"]["label"] for node in graph["nodes"]}
        self.assertIn("ACME", labels)
        self.assertIn("Tier1 Metals", labels)
        edge_labels = {edge["data"]["label"] for edge in graph["edges"]}
        self.assertIn("tier 1", edge_labels)
        self.assertIn("source", edge_labels)

    def test_build_answer_graph_uses_sanctions_matches_when_graphrag_is_absent(self) -> None:
        result = {
            "query_id": "query-456",
            "route_results": {
                "sanctions": {
                    "evidence": {
                        "matches": [
                            {
                                "supplier_name": "Northwind Components",
                                "matched_name": "Northwind Components LLC",
                                "match_type": "primary_exact",
                            }
                        ]
                    }
                }
            },
        }

        graph = build_answer_graph(result)

        self.assertEqual(2, graph["stats"]["node_count"])
        self.assertEqual(1, graph["stats"]["edge_count"])
        self.assertEqual("matched", graph["edges"][0]["data"]["label"])
