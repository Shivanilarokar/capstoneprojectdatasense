from __future__ import annotations

from datetime import date, datetime
from unittest import TestCase

from backend.ingestion.load_ofac_bis import transform_ofac_bis_row


class OfacBisLoaderTests(TestCase):
    def test_transform_ofac_bis_row_maps_primary_columns(self) -> None:
        row = {
            "Entity ID": "36",
            "Primary Name": "AEROCARIBBEAN AIRLINES",
            "Entity Type": "Entity",
            "Sanctions Program(s)": "CUBA",
            "Sanctions Type": "Block",
            "Date Published": "1986-12-10",
            "Aliases": "A.K.A.: AERO-CARIBBEAN",
            "Date of Birth": "1980-01-01",
            "Place of Birth": "Havana, Cuba",
            "Nationality": None,
            "Citizenship": None,
            "Gender": "Unknown",
            "Address(es)": "Havana, Cuba",
            "Document IDs": None,
        }

        record = transform_ofac_bis_row("tenant-dev", "sdn_data.xlsx", row)

        self.assertEqual("tenant-dev", record["tenant_id"])
        self.assertEqual("36", record["source_entity_id"])
        self.assertEqual("AEROCARIBBEAN AIRLINES", record["primary_name"])
        self.assertEqual("CUBA", record["sanctions_programs"])
        self.assertEqual(date(1986, 12, 10), record["date_published"])
        self.assertEqual(date(1980, 1, 1), record["date_of_birth"])
        self.assertEqual("Havana, Cuba", record["place_of_birth"])
        self.assertEqual("Unknown", record["gender"])
        self.assertEqual("Havana, Cuba", record["address_text"])
        self.assertEqual("sdn_data.xlsx", record["source_file_name"])

        self.assertEqual("ofac_sdn", record["source_list_name"])
        self.assertEqual(1, record["alias_count"])
        self.assertEqual(1, record["address_count"])

    def test_transform_ofac_bis_row_accepts_excel_date_objects(self) -> None:
        row = {
            "Entity ID": "36",
            "Primary Name": "AEROCARIBBEAN AIRLINES",
            "Entity Type": "Entity",
            "Sanctions Program(s)": "CUBA",
            "Sanctions Type": "Block",
            "Date Published": datetime(1986, 12, 10, 9, 30, 0),
            "Aliases": "",
            "Date of Birth": date(1980, 1, 1),
            "Place of Birth": "Havana, Cuba",
            "Nationality": None,
            "Citizenship": None,
            "Gender": "Unknown",
            "Address(es)": "Havana, Cuba",
            "Document IDs": None,
        }

        record = transform_ofac_bis_row("tenant-dev", "sdn_data.xlsx", row)

        self.assertEqual(date(1986, 12, 10), record["date_published"])
        self.assertEqual(date(1980, 1, 1), record["date_of_birth"])



