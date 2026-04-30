from __future__ import annotations

from unittest import TestCase

from backend.nlsql.presentation import (
    build_evidence_lines,
    format_rows_for_display,
    render_answer_first,
    summarize_methodology,
)


class PresentationTests(TestCase):
    def test_render_answer_first_outputs_expected_sections(self) -> None:
        text = render_answer_first(
            question="Which states had the highest storm damage?",
            answer="Texas had the highest damage.",
            methodology="Summed damage_property_usd by state.",
            evidence_lines=["1. Texas | $1,200,000"],
        )

        self.assertIn("Question", text)
        self.assertIn("Answer", text)
        self.assertIn("How It Was Computed", text)
        self.assertIn("Evidence", text)
        self.assertIn("1. Texas | $1,200,000", text)

    def test_format_rows_for_display_formats_currency_and_dates(self) -> None:
        rows = format_rows_for_display(
            [
                {
                    "state": "Texas",
                    "total_damage_usd": 1200000.0,
                    "posted_date": "2024-01-02",
                }
            ]
        )

        self.assertEqual("$1,200,000", rows[0]["total_damage_usd"])
        self.assertEqual("2024-01-02", rows[0]["posted_date"])

    def test_build_evidence_lines_uses_first_keys(self) -> None:
        evidence = build_evidence_lines(
            [
                {"state": "Texas", "total_damage": "$1,200,000"},
                {"state": "Florida", "total_damage": "$950,000"},
            ]
        )

        self.assertEqual(
            [
                "1. Texas | $1,200,000",
                "2. Florida | $950,000",
            ],
            evidence,
        )

    def test_format_rows_for_display_formats_percentages(self) -> None:
        rows = format_rows_for_display([{"match_rate": 0.125}])

        self.assertEqual("12.5%", rows[0]["match_rate"])

    def test_summarize_methodology_mentions_route(self) -> None:
        text = summarize_methodology(
            route="weather",
            sql=(
                "SELECT state, SUM(damage_property_usd) AS total_damage "
                "FROM source_noaa_storm_events WHERE tenant_id = %(tenant_id)s GROUP BY state"
            ),
            row_count=2,
        )

        self.assertIn("NOAA storm events", text)
        self.assertIn("2 row", text)
        self.assertIn("aggregated", text)



