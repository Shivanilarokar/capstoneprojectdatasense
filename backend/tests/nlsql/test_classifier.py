from __future__ import annotations

from unittest import TestCase

from backend.nlsql.classifier import classify_question


class ClassifierTests(TestCase):
    def test_classifies_weather_question(self) -> None:
        result = classify_question("Which states had the highest storm damage?")

        self.assertEqual("weather", result.route)
        self.assertIn("weather", result.reason)
        self.assertEqual(["source_noaa_storm_events"], result.preferred_tables)

    def test_classifies_trade_question(self) -> None:
        result = classify_question("Which countries had the highest export value in 2023?")

        self.assertEqual("trade", result.route)
        self.assertEqual(["source_comtrade_flows"], result.preferred_tables)

    def test_classifies_cross_source_question(self) -> None:
        result = classify_question(
            "Which companies appear in both FDA warning letters and the OFAC SDN list?"
        )

        self.assertEqual("cross_source", result.route)
        self.assertEqual(
            ["source_fda_warning_letters", "source_ofac_sdn_entities"],
            result.preferred_tables,
        )



