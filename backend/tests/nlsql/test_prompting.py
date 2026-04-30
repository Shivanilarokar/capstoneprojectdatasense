from __future__ import annotations

from unittest import TestCase

from backend.nlsql.prompting import build_answer_prompt, build_sql_generation_prompt, build_sql_repair_prompt


class PromptingTests(TestCase):
    def test_build_sql_generation_prompt_embeds_question_schema_and_route_examples(self) -> None:
        prompt = build_sql_generation_prompt(
            question="Which states had the highest storm damage?",
            schema_text="Table: source_noaa_storm_events\n- state (text)",
            route="weather",
            helper_text="",
        )
        self.assertIn("Which states had the highest storm damage?", prompt)
        self.assertIn("source_noaa_storm_events", prompt)
        self.assertIn("Route: weather", prompt)
        self.assertIn("Example", prompt)
        self.assertIn("Route-specific guidance", prompt)

    def test_build_sql_repair_prompt_embeds_db_error(self) -> None:
        prompt = build_sql_repair_prompt(
            question="How many FDA warnings per company?",
            schema_text="Table: source_fda_warning_letters\n- company_name (text)",
            route="fda",
            helper_text="Cross-source helper not required.",
            bad_sql="SELECT company FROM source_fda_warning_letters",
            db_error='column "company" does not exist',
        )
        self.assertIn('column "company" does not exist', prompt)
        self.assertIn("SELECT company", prompt)
        self.assertIn("Route: fda", prompt)

    def test_build_sql_generation_prompt_for_cross_source_mentions_helper_strategy(self) -> None:
        prompt = build_sql_generation_prompt(
            question="Which companies appear in both FDA warning letters and the OFAC SDN list?",
            schema_text=(
                "Table: source_fda_warning_letters\n- company_name_normalized (text)\n"
                "Table: source_ofac_sdn_entities\n- aliases (text)"
            ),
            route="cross_source",
            helper_text="Cross-source helper",
        )

        self.assertIn("company_name_normalized", prompt)
        self.assertIn("aliases", prompt)
        self.assertIn("deterministic normalized-name", prompt)

    def test_build_sql_generation_prompt_requires_tenant_filter_parameter(self) -> None:
        prompt = build_sql_generation_prompt(
            question="Which states had the highest storm damage?",
            schema_text="Table: source_noaa_storm_events\n- tenant_id (text)\n- state (text)",
            route="weather",
            helper_text="",
        )
        self.assertIn("tenant_id", prompt)
        self.assertIn("%(tenant_id)s", prompt)

    def test_build_answer_prompt_includes_methodology_and_formatted_rows(self) -> None:
        prompt = build_answer_prompt(
            question="Which states had the highest storm damage?",
            sql="SELECT state, SUM(damage_property_usd) AS total_damage FROM source_noaa_storm_events",
            rows=[{"state": "Texas", "total_damage": "$1,200,000"}],
            route="weather",
            methodology="Summed damage_property_usd by state.",
        )

        self.assertIn("Route: weather", prompt)
        self.assertIn("How It Was Computed", prompt)
        self.assertIn("$1,200,000", prompt)
        self.assertIn("If no rows are returned", prompt)



