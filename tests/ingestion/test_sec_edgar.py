from __future__ import annotations

from unittest import TestCase

from config import PROJECT_ROOT
from ingestion.sec_edgar import (
    DEFAULT_COMPANIES_JSON,
    DEFAULT_SEC_DATA_DIR,
    EdgarClient,
    parse_extract_args,
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
