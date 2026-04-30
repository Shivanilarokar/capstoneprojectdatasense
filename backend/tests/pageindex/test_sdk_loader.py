from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest import TestCase
from uuid import uuid4

from backend.config import PROJECT_ROOT
from backend.pageindex.sdk_loader import (
    LocalMarkdownAdapter,
    is_pageindex_cloud_unavailable_error,
    is_pageindex_limit_error,
)


class PageIndexSdkLoaderTests(TestCase):
    def setUp(self) -> None:
        self.tmp_dir = PROJECT_ROOT / "tmp" / f"pageindex-sdk-loader-{uuid4().hex}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))

    def test_local_markdown_adapter_indexes_markdown_and_exposes_tree_and_content(self) -> None:
        markdown_path = self.tmp_dir / "sample.md"
        markdown_path.write_text(
            "\n".join(
                [
                    "# Sample 10-K",
                    "",
                    "## Item 1A - Risk Factors",
                    "Supply chain disruptions may affect production capacity.",
                    "Supplier concentration creates dependency risk.",
                    "",
                    "### Semiconductor Supply",
                    "Single-source chip constraints could delay shipments.",
                    "",
                    "## Item 7 - MD&A",
                    "Management continues diversifying the supplier base.",
                ]
            ),
            encoding="utf-8",
        )

        adapter = LocalMarkdownAdapter(workspace=self.tmp_dir / "workspace")
        doc_id = adapter.index(str(markdown_path))

        tree = json.loads(adapter.get_document_structure(doc_id))
        self.assertEqual("Sample 10-K", tree[0]["title"])
        self.assertTrue(tree[0]["nodes"])
        self.assertEqual("Item 1A - Risk Factors", tree[0]["nodes"][0]["title"])

        selector = f"{tree[0]['nodes'][0]['start_index']}-{tree[0]['nodes'][0]['end_index']}"
        rows = json.loads(adapter.get_page_content(doc_id, selector))
        joined = "\n".join(str(row["content"]) for row in rows)
        self.assertIn("Supply chain disruptions", joined)
        self.assertIn("Supplier concentration", joined)

    def test_is_pageindex_limit_error_matches_limitreached_payloads(self) -> None:
        self.assertTrue(is_pageindex_limit_error(RuntimeError('{"detail":"LimitReached"}')))
        self.assertTrue(is_pageindex_limit_error(RuntimeError("limit reached")))
        self.assertFalse(is_pageindex_limit_error(RuntimeError("other failure")))

    def test_is_pageindex_cloud_unavailable_error_matches_network_failures(self) -> None:
        self.assertTrue(
            is_pageindex_cloud_unavailable_error(
                RuntimeError("HTTPSConnectionPool(host='api.pageindex.ai'): Max retries exceeded")
            )
        )
        self.assertTrue(
            is_pageindex_cloud_unavailable_error(
                RuntimeError("Failed to submit document: {\"detail\":\"LimitReached\"}")
            )
        )
        self.assertFalse(is_pageindex_cloud_unavailable_error(RuntimeError("file not found")))




