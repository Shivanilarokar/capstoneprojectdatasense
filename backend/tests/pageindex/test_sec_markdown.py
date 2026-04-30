from __future__ import annotations

from pathlib import Path
import shutil
from unittest import TestCase
from uuid import uuid4

from backend.config import PROJECT_ROOT
from backend.pageindex.models import CompanySectionDoc
from backend.pageindex.sec_markdown import materialize_markdown_docs


class SecMarkdownTests(TestCase):
    def test_materialize_markdown_docs_uses_unique_paths_per_filing(self) -> None:
        docs = [
            CompanySectionDoc(
                ticker="AAPL",
                company_name="Apple Inc.",
                cik="0000320193",
                accession_number="000032019325000079",
                filing_date="2025-10-31",
                filing_document_url="https://example.com/aapl-2025",
                item1="business",
                item1a="risk",
                item7="mda",
                item7a="market risk",
                item8="financials",
                item16="summary",
                notes="notes",
            ),
            CompanySectionDoc(
                ticker="AAPL",
                company_name="Apple Inc.",
                cik="0000320193",
                accession_number="000032019324000123",
                filing_date="2024-11-01",
                filing_document_url="https://example.com/aapl-2024",
                item1="business",
                item1a="risk",
                item7="mda",
                item7a="market risk",
                item8="financials",
                item16="summary",
                notes="notes",
            ),
        ]

        tmp_dir = PROJECT_ROOT / "tmp" / f"pageindex-sec-markdown-{uuid4().hex}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

        registry = materialize_markdown_docs(docs, tmp_dir)

        self.assertEqual(2, len(registry))
        self.assertEqual(2, len({row["markdown_path"] for row in registry}))
        self.assertEqual(
            ["2025-10-31", "2024-11-01"],
            [row["filing_date"] for row in registry],
        )
        self.assertEqual(
            ["000032019325000079", "000032019324000123"],
            [row["accession_number"] for row in registry],
        )
        for row in registry:
            self.assertTrue(Path(row["markdown_path"]).exists())




