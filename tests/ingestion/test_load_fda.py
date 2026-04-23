from __future__ import annotations

from unittest import TestCase

from ingestion.load_fda import transform_fda_row


class FdaLoaderTests(TestCase):
    def test_transform_fda_row_uses_record_hash_primary_key(self) -> None:
        row = {
            "Posted Date": "12/02/2025",
            "Letter Issue Date": "11/12/2025",
            "Company Name": "Rhyz Analytical Labs",
            "Issuing Office": "Center for Drug Evaluation and Research (CDER)",
            "Subject": "CGMP/Finished Pharmaceuticals/Adulterated",
            "Response Letter": None,
            "Closeout Letter": None,
        }

        record = transform_fda_row("tenant-dev", "warning-letters.xlsx", row)

        self.assertEqual("tenant-dev", record["tenant_id"])
        self.assertEqual("Rhyz Analytical Labs", record["company_name"])
        self.assertTrue(record["source_record_hash"])
