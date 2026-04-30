from __future__ import annotations

import json
import shutil
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from backend.config import PROJECT_ROOT
from backend.pageindex.pipeline import run_pipeline


class _LimitReachedClient:
    def __init__(self) -> None:
        self.documents = {}

    def index(self, *_args, **_kwargs):
        raise RuntimeError('Failed to submit document: {"detail":"LimitReached"}')


class _ChatClient:
    def __init__(self) -> None:
        self.documents = {}
        self.chat_calls = []
        self.document_calls = []

    def index(self, file_path: str, mode: str = "auto") -> str:
        _ = mode
        doc_id = "pi-aapl-doc"
        self.documents[doc_id] = {"path": file_path}
        return doc_id

    def get_document(self, doc_id: str):
        self.document_calls.append(doc_id)
        return {"id": doc_id, "status": "completed", "pageNum": 136}

    def is_retrieval_ready(self, doc_id: str) -> bool:
        _ = doc_id
        return True

    def chat_completions(
        self,
        *,
        messages,
        stream=False,
        doc_id=None,
        temperature=None,
        stream_metadata=False,
        enable_citations=False,
    ):
        self.chat_calls.append(
            {
                "messages": messages,
                "stream": stream,
                "doc_id": doc_id,
                "temperature": temperature,
                "stream_metadata": stream_metadata,
                "enable_citations": enable_citations,
            }
        )
        if not stream or not stream_metadata:
            return {"choices": [{"message": {"content": "unused"}}]}

        chunks = [
            {"choices": [{"delta": {"content": "Question:\nWhat risks are disclosed?\n\n"}}]},
            {
                "choices": [
                    {
                        "delta": {
                            "content": "Answer:\n- Supplier concentration risk <doc=AAPL_2025-10-31_unknown-accession_10k_supply_chain.md;page=12>\n\n"
                        }
                    }
                ]
            },
            {
                "object": "chat.completion.citations",
                "citations": [
                    {
                        "doc": "AAPL_2025-10-31_unknown-accession_10k_supply_chain.md",
                        "page": 12,
                    }
                ],
            },
            {
                "choices": [
                    {
                        "delta": {
                            "content": "Evidence:\n- Item 1A discusses supply chain disruptions <doc=AAPL_2025-10-31_unknown-accession_10k_supply_chain.md;page=12>\n\nSources:\n- <doc=AAPL_2025-10-31_unknown-accession_10k_supply_chain.md;page=12>\n"
                        }
                    }
                ]
            },
        ]
        return iter(chunks)


class PageIndexPipelineFallbackTests(TestCase):
    def setUp(self) -> None:
        self.tmp_dir = PROJECT_ROOT / "tmp" / f"pageindex-pipeline-{uuid4().hex}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))

    def _write_sections(self, filename: str = "sections.json") -> object:
        sections_json = self.tmp_dir / filename
        sections_json.write_text(
            json.dumps(
                [
                    {
                        "ticker": "AAPL",
                        "company_name": "Apple Inc.",
                        "cik": "0000320193",
                        "filing_date": "2025-10-31",
                        "filing_document_url": "https://example.com/aapl",
                        "sections": {
                            "item1": "Item 1. Business overview.",
                            "item1a": "Item 1A. Supply chain disruptions may affect production.",
                            "item7": "Item 7. Management discusses supplier diversification.",
                            "item7a": "",
                            "item8": "Item 8. Notes to financial statements.",
                            "item16": "",
                        },
                    }
                ]
            ),
            encoding="utf-8",
        )
        return sections_json

    def test_run_pipeline_raises_cloud_error_when_limit_is_reached(self) -> None:
        sections_json = self._write_sections()
        fake_config = SimpleNamespace(pageindex_api_key="pi-test")

        with patch("backend.pageindex.pipeline.load_app_config", return_value=fake_config), patch(
            "backend.pageindex.pipeline.resolve_pageindex_key", return_value="pi-test"
        ), patch("backend.pageindex.pipeline.init_pageindex_client", return_value=_LimitReachedClient()):
            with self.assertRaisesRegex(RuntimeError, "usage quota appears to be exhausted"):
                run_pipeline(
                    sections_json_path=sections_json,
                    docs_dir=self.tmp_dir / "docs",
                    workspace=self.tmp_dir / "workspace",
                    output_dir=self.tmp_dir / "output",
                    question="What supply chain risks are disclosed by Apple?",
                    openai_model="unused",
                    index_model=None,
                    retrieve_model=None,
                    reindex=False,
                    docs_only=False,
                    max_context_chars=5000,
                    index_mode="md",
                    max_docs=1,
                    max_depth=3,
                    max_nodes_per_level=2,
                    max_candidate_nodes=10,
                )

    def test_run_pipeline_uses_pageindex_chat_and_persists_answer_artifact(self) -> None:
        sections_json = self._write_sections("sections_chat.json")
        fake_config = SimpleNamespace(pageindex_api_key="pi-test")
        fake_client = _ChatClient()
        streamed: list[str] = []

        with patch("backend.pageindex.pipeline.load_app_config", return_value=fake_config), patch(
            "backend.pageindex.pipeline.resolve_pageindex_key", return_value="pi-test"
        ), patch("backend.pageindex.pipeline.init_pageindex_client", return_value=fake_client):
            summary = run_pipeline(
                sections_json_path=sections_json,
                docs_dir=self.tmp_dir / "docs_chat",
                workspace=self.tmp_dir / "workspace_chat",
                output_dir=self.tmp_dir / "output_chat",
                question="What supply chain risks are disclosed by Apple?",
                openai_model="unused",
                index_model=None,
                retrieve_model=None,
                reindex=False,
                docs_only=False,
                max_context_chars=5000,
                index_mode="md",
                max_docs=1,
                max_depth=3,
                max_nodes_per_level=2,
                max_candidate_nodes=10,
                stream_handler=streamed.append,
            )

        self.assertEqual("cloud", summary["adapter_mode"])
        self.assertEqual(1, len(fake_client.chat_calls))
        self.assertEqual(["pi-aapl-doc"], fake_client.document_calls)
        self.assertTrue(fake_client.chat_calls[0]["enable_citations"])
        self.assertTrue(fake_client.chat_calls[0]["stream"])
        self.assertTrue(fake_client.chat_calls[0]["stream_metadata"])
        self.assertEqual(["pi-aapl-doc"], fake_client.chat_calls[0]["doc_id"])
        self.assertEqual("user", fake_client.chat_calls[0]["messages"][0]["role"])
        self.assertTrue("".join(streamed).startswith("Question:"))

        qa_result = json.loads((self.tmp_dir / "output_chat" / "qa_result.json").read_text(encoding="utf-8"))
        self.assertEqual("pageindex_cloud_chat", qa_result["chat_mode"])
        self.assertIn("Supplier concentration risk", qa_result["answer"])
        self.assertEqual(
            ["<doc=AAPL_2025-10-31_unknown-accession_10k_supply_chain.md;page=12>"],
            qa_result["citations"],
        )
        self.assertEqual(1, len(qa_result["citation_events"]))
        self.assertEqual("pi-aapl-doc", qa_result["doc_ids"][0])




