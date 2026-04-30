from __future__ import annotations

from datetime import date, datetime
from unittest import TestCase

from backend.ingestion.load_fda import transform_fda_row


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
        self.assertEqual(date(2025, 12, 2), record["posted_date"])
        self.assertEqual(date(2025, 11, 12), record["letter_issue_date"])
        self.assertEqual("Rhyz Analytical Labs", record["company_name"])
        self.assertTrue(record["source_record_hash"])
        self.assertEqual("manufacturing_quality", record["risk_category"])
        self.assertEqual("high", record["severity"])

    def test_transform_fda_row_accepts_excel_date_objects(self) -> None:
        row = {
            "Posted Date": datetime(2025, 12, 2, 14, 15, 0),
            "Letter Issue Date": date(2025, 11, 12),
            "Company Name": "Rhyz Analytical Labs",
            "Issuing Office": "Center for Drug Evaluation and Research (CDER)",
            "Subject": "CGMP/Finished Pharmaceuticals/Adulterated",
            "Response Letter": None,
            "Closeout Letter": None,
        }

        record = transform_fda_row("tenant-dev", "warning-letters.xlsx", row)

        self.assertEqual(date(2025, 12, 2), record["posted_date"])
        self.assertEqual(date(2025, 11, 12), record["letter_issue_date"])



