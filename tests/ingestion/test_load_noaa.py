from __future__ import annotations

from unittest import TestCase

from ingestion.load_noaa import parse_damage_value, transform_noaa_row


class NoaaLoaderTests(TestCase):
    def test_parse_damage_value_handles_k_m_b_suffixes(self) -> None:
        self.assertEqual(250000.0, parse_damage_value("250K"))
        self.assertEqual(1200000.0, parse_damage_value("1.2M"))
        self.assertEqual(3000000000.0, parse_damage_value("3B"))

    def test_transform_noaa_row_maps_core_fields(self) -> None:
        row = {
            "EVENT_ID": "10096222",
            "EPISODE_ID": "",
            "STATE": "OKLAHOMA",
            "YEAR": "1950",
            "MONTH_NAME": "April",
            "EVENT_TYPE": "Tornado",
            "CZ_NAME": "WASHITA",
            "BEGIN_DATE_TIME": "28-APR-50 14:45:00",
            "END_DATE_TIME": "28-APR-50 14:45:00",
            "DAMAGE_PROPERTY": "250K",
            "DAMAGE_CROPS": "0",
            "BEGIN_LAT": "35.12",
            "BEGIN_LON": "-99.20",
            "END_LAT": "35.17",
            "END_LON": "-99.20",
            "EPISODE_NARRATIVE": "",
            "EVENT_NARRATIVE": "",
        }

        record = transform_noaa_row("tenant-dev", "storm.csv", row)

        self.assertEqual(10096222, record["event_id"])
        self.assertEqual("OKLAHOMA", record["state"])
        self.assertEqual("Tornado", record["event_type"])
        self.assertEqual(250000.0, record["damage_property_usd"])
