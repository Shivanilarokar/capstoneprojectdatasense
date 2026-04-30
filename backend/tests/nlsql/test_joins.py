from __future__ import annotations

from unittest import TestCase

from backend.nlsql.joins import helper_text_for_route, normalized_alias_blob_expression


class JoinTests(TestCase):
    def test_cross_source_helper_mentions_company_normalized_and_alias_matching(self) -> None:
        helper = helper_text_for_route("cross_source")

        self.assertIn("company_name_normalized", helper)
        self.assertIn("aliases", helper)
        self.assertIn("LIKE '%' || fda_normalized || '%'", helper)

    def test_normalized_alias_blob_expression_keeps_text_normalization(self) -> None:
        expression = normalized_alias_blob_expression("aliases")

        self.assertIn("lower(coalesce(aliases", expression)
        self.assertIn("regexp_replace", expression)



