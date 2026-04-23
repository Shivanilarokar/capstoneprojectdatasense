from __future__ import annotations

from unittest import TestCase

from sanctions.matcher import extract_candidate_entities, normalize_name, parse_aliases, screen_entities


class SanctionsMatcherTests(TestCase):
    def test_normalize_name_collapses_case_and_punctuation(self) -> None:
        self.assertEqual("acme global llc", normalize_name("ACME, Global LLC"))

    def test_parse_aliases_splits_semicolon_pipe_and_newline_delimiters(self) -> None:
        self.assertEqual(
            ["Acme Global", "Acme Trading", "AG Holdings"],
            parse_aliases("Acme Global; Acme Trading | AG Holdings"),
        )

    def test_extract_candidate_entities_prefers_quoted_names(self) -> None:
        self.assertEqual(
            ["Acme Global"],
            extract_candidate_entities('Is "Acme Global" sanctioned?'),
        )

    def test_screen_entities_finds_primary_and_alias_matches(self) -> None:
        rows = [
            {
                "source_entity_id": "100",
                "primary_name": "ACME TRADING LLC",
                "aliases": "Acme Trading; Acme Global",
                "sanctions_programs": "SDN",
                "sanctions_type": "Entity",
            }
        ]

        result = screen_entities("Is Acme Global sanctioned?", rows, entity_names=["Acme Global"])

        self.assertEqual(["Acme Global"], result["entities"])
        self.assertEqual([], result["unmatched_entities"])
        self.assertEqual("alias_exact", result["matches"][0]["match_type"])
        self.assertEqual("ACME TRADING LLC", result["matches"][0]["matched_name"])

    def test_screen_entities_marks_unmatched_entities(self) -> None:
        result = screen_entities(
            "Screen Globex Holdings",
            [],
            entity_names=["Globex Holdings"],
        )

        self.assertEqual(["Globex Holdings"], result["entities"])
        self.assertEqual(["Globex Holdings"], result["unmatched_entities"])
        self.assertEqual([], result["matches"])

