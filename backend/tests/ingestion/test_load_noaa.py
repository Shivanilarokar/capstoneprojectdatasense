from __future__ import annotations

from datetime import datetime
from unittest import TestCase

from backend.ingestion.load_noaa import parse_damage_value, transform_noaa_row


class NoaaLoaderTests(TestCase):
    def test_parse_damage_value_handles_k_m_b_suffixes(self) -> None:
        self.assertEqual(250000.0, parse_damage_value("250K"))
        self.assertEqual(1200000.0, parse_damage_value("1.2M"))
        self.assertEqual(3000000000.0, parse_damage_value("3B"))

    def test_transform_noaa_row_maps_core_fields(self) -> None:
        row = {
            "BEGIN_YEARMONTH": "195004",
            "BEGIN_DAY": "28",
            "BEGIN_TIME": "1445",
            "END_YEARMONTH": "195004",
            "END_DAY": "28",
            "END_TIME": "1445",
            "EVENT_ID": "10096222",
            "EPISODE_ID": "",
            "STATE": "OKLAHOMA",
            "STATE_FIPS": "40",
            "YEAR": "1950",
            "MONTH_NAME": "April",
            "EVENT_TYPE": "Tornado",
            "CZ_TYPE": "C",
            "CZ_FIPS": "149",
            "CZ_NAME": "WASHITA",
            "WFO": "",
            "BEGIN_DATE_TIME": "28-APR-50 14:45:00",
            "CZ_TIMEZONE": "CST",
            "END_DATE_TIME": "28-APR-50 14:45:00",
            "INJURIES_DIRECT": "0",
            "INJURIES_INDIRECT": "0",
            "DEATHS_DIRECT": "0",
            "DEATHS_INDIRECT": "0",
            "DAMAGE_PROPERTY": "250K",
            "DAMAGE_CROPS": "0",
            "SOURCE": "",
            "MAGNITUDE": "0",
            "MAGNITUDE_TYPE": "",
            "FLOOD_CAUSE": "",
            "CATEGORY": "",
            "TOR_F_SCALE": "F3",
            "TOR_LENGTH": "3.4",
            "TOR_WIDTH": "400",
            "TOR_OTHER_WFO": "",
            "TOR_OTHER_CZ_STATE": "",
            "TOR_OTHER_CZ_FIPS": "",
            "TOR_OTHER_CZ_NAME": "",
            "BEGIN_RANGE": "",
            "BEGIN_AZIMUTH": "",
            "BEGIN_LOCATION": "",
            "END_RANGE": "",
            "END_AZIMUTH": "",
            "END_LOCATION": "",
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
        self.assertEqual(195004, record["begin_yearmonth"])
        self.assertEqual(1445, record["begin_time"])
        self.assertEqual(40, record["state_fips"])
        self.assertEqual("C", record["cz_type"])
        self.assertEqual(149, record["cz_fips"])
        self.assertEqual("Tornado", record["event_type"])
        self.assertEqual("CST", record["cz_timezone"])
        self.assertEqual(0, record["injuries_direct"])
        self.assertEqual(0.0, record["magnitude"])
        self.assertEqual("F3", record["tor_f_scale"])
        self.assertEqual(3.4, record["tor_length"])
        self.assertEqual(400.0, record["tor_width"])
        self.assertEqual(datetime(1950, 4, 28, 14, 45, 0), record["begin_date_time"])
        self.assertEqual(datetime(1950, 4, 28, 14, 45, 0), record["end_date_time"])
        self.assertEqual(250000.0, record["damage_property_usd"])
        self.assertEqual(35.145, record["event_mid_lat"])
        self.assertEqual(-99.2, record["event_mid_lon"])



