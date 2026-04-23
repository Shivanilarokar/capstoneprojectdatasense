from __future__ import annotations

from unittest import TestCase

from ingestion.load_ofac_bis import transform_ofac_bis_row


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
            "Nationality": None,
            "Citizenship": None,
            "Address(es)": "Havana, Cuba",
            "Document IDs": None,
        }

        record = transform_ofac_bis_row("tenant-dev", "sdn_data.xlsx", row)

        self.assertEqual("tenant-dev", record["tenant_id"])
        self.assertEqual("36", record["source_entity_id"])
        self.assertEqual("AEROCARIBBEAN AIRLINES", record["primary_name"])
        self.assertEqual("CUBA", record["sanctions_programs"])
        self.assertEqual("Havana, Cuba", record["address_text"])
        self.assertEqual("sdn_data.xlsx", record["source_file_name"])
