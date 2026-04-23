from __future__ import annotations

from unittest import TestCase

from nlsql.prompting import build_sql_generation_prompt, build_sql_repair_prompt


class PromptingTests(TestCase):
    def test_build_sql_generation_prompt_embeds_question_and_schema(self) -> None:
        prompt = build_sql_generation_prompt(
            question="Which states had the highest storm damage?",
            schema_text="Table: source_noaa_storm_events\n- state (text)",
        )
        self.assertIn("Which states had the highest storm damage?", prompt)
        self.assertIn("source_noaa_storm_events", prompt)

    def test_build_sql_repair_prompt_embeds_db_error(self) -> None:
        prompt = build_sql_repair_prompt(
            question="How many FDA warnings per company?",
            schema_text="Table: source_fda_warning_letters\n- company_name (text)",
            bad_sql="SELECT company FROM source_fda_warning_letters",
            db_error='column "company" does not exist',
        )
        self.assertIn('column "company" does not exist', prompt)
        self.assertIn("SELECT company", prompt)

    def test_build_sql_generation_prompt_requires_tenant_filter_parameter(self) -> None:
        prompt = build_sql_generation_prompt(
            question="Which states had the highest storm damage?",
            schema_text="Table: source_noaa_storm_events\n- tenant_id (text)\n- state (text)",
        )
        self.assertIn("tenant_id", prompt)
        self.assertIn("%(tenant_id)s", prompt)
