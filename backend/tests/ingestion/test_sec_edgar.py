from __future__ import annotations

import json
from pathlib import Path
import shutil
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from backend.config import PROJECT_ROOT
from backend.ingestion.sec_edgar_ingestion import (
    DEFAULT_COMPANIES_JSON,
    DEFAULT_SEC_DATA_DIR,
    EdgarClient,
    parse_extract_args,
    run_batch_ingestion,
)


class SecEdgarTests(TestCase):
    def test_default_sec_paths_point_to_data_ingestion_root(self) -> None:
        self.assertEqual("data/ingestion/sec/edgar", DEFAULT_SEC_DATA_DIR)
        self.assertEqual("data/ingestion/sec/companies.json", DEFAULT_COMPANIES_JSON)

    def test_edgar_client_requires_contact_email(self) -> None:
        with self.assertRaises(ValueError):
            EdgarClient("SupplyChainNexus")

    def test_parse_extract_args_defaults_to_data_ingestion_sec_outputs(self) -> None:
        args = parse_extract_args([])

        self.assertEqual("data/ingestion/sec/companies.json", args.companies_json)
        self.assertEqual("data/ingestion/sec/extracted_10k_sections.json", args.output_json)

    def test_legacy_sec_edgar_source_files_are_removed(self) -> None:
        legacy_root = PROJECT_ROOT / "src" / "ingestion" / "Sec_Edgar10kfillings"
        self.assertFalse((legacy_root / "EdgarClient.py").exists())
        self.assertFalse((legacy_root / "extract_10k_sections.py").exists())

    def test_run_batch_ingestion_writes_all_filings_to_companies_json(self) -> None:
        class FakeEdgarClient:
            def __init__(self, user_agent: str):
                self.user_agent = user_agent

            def ingest_company(self, **_kwargs):
                return {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "cik": "0000320193",
                    "filings": [
                        {
                            "accession_number": "000032019325000079",
                            "filing_type": "10-K",
                            "filing_date": "2025-10-31",
                            "period_of_report": "2025-09-27",
                            "filing_document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
                            "primary_document_path": "E:/tmp/aapl-2025-primary_document",
                            "primary_document_saved": True,
                        },
                        {
                            "accession_number": "000032019324000123",
                            "filing_type": "10-K",
                            "filing_date": "2024-11-01",
                            "period_of_report": "2024-09-28",
                            "filing_document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
                            "primary_document_path": "E:/tmp/aapl-2024-primary_document",
                            "primary_document_saved": True,
                        },
                    ],
                }

        tmp_dir = PROJECT_ROOT / "tmp" / f"sec-edgar-test-{uuid4().hex}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
        companies_path = tmp_dir / "companies.json"
        with patch("backend.ingestion.sec_edgar_ingestion.EdgarClient", FakeEdgarClient):
            run_batch_ingestion(
                user_agent="SupplyChainNexus test@example.com",
                tickers=["AAPL"],
                data_dir=str(tmp_dir / "edgar"),
                companies_output_path=str(companies_path),
                max_filings_per_ticker=2,
            )

        rows = json.loads(companies_path.read_text(encoding="utf-8"))
        self.assertEqual(2, len(rows))
        self.assertEqual(
            ["2025-10-31", "2024-11-01"],
            [row["filing_date"] for row in rows],
        )
        self.assertEqual(
            ["000032019325000079", "000032019324000123"],
            [row["accession_number"] for row in rows],
        )
        self.assertTrue(all(row["downloaded"] for row in rows))




