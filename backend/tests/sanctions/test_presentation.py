from __future__ import annotations

from unittest import TestCase

from backend.sanctions.presentation import render_sanctions_output


class SanctionsPresentationTests(TestCase):
    def test_render_sanctions_output_formats_matches_and_freshness(self) -> None:
        result = {
            "question": "Is Acme Global sanctioned?",
            "answer": (
                "Sanctions screening found matches: Acme Global matched ACME TRADING LLC "
                "(alias_exact via alias `Acme Global`, SDN, score=0.99)."
            ),
            "evidence": {
                "matches": [
                    {
                        "entity_name": "Acme Global",
                        "matched_name": "ACME TRADING LLC",
                        "match_type": "alias_exact",
                        "score": 0.99,
                        "sanctions_programs": "SDN",
                    }
                ],
                "review_candidates": [
                    {
                        "entity_name": "Shadow Match",
                        "matched_name": "SHADOW MATCH LTD",
                    }
                ],
            },
            "freshness": {
                "latest_loaded_at": "2026-04-23T10:00:00Z",
            },
            "warnings": [],
        }

        text = render_sanctions_output(result)

        self.assertIn("Question", text)
        self.assertIn("Answer", text)
        self.assertIn("Matched Entities", text)
        self.assertIn("1. Acme Global -> ACME TRADING LLC | alias_exact | score=0.99 | program=SDN", text)
        self.assertIn("Freshness", text)
        self.assertIn("Latest loaded at: 2026-04-23T10:00:00Z", text)
        self.assertNotIn("Review Candidates", text)
        self.assertNotIn("Shadow Match", text)

    def test_render_sanctions_output_shows_none_when_no_matches(self) -> None:
        result = {
            "question": "Is Globex sanctioned?",
            "answer": "No sanctions matches were found for: Globex.",
            "evidence": {
                "matches": [],
                "review_candidates": [],
            },
            "freshness": {
                "latest_loaded_at": None,
            },
            "warnings": ["No entity names were extracted from the question for sanctions screening."],
        }

        text = render_sanctions_output(result)

        self.assertIn("Matched Entities", text)
        self.assertIn("None", text)
        self.assertIn("Freshness", text)
        self.assertIn("Latest loaded at: unavailable", text)
        self.assertIn("Warnings", text)




