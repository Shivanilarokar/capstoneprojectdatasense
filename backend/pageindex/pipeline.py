"""Top-level orchestration for SEC -> PageIndex cloud chat pipeline."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

from backend.config import load_app_config
from .json_utils import write_json
from .sdk_loader import (
    describe_pageindex_cloud_error,
    init_pageindex_client,
    is_pageindex_cloud_unavailable_error,
    is_pageindex_limit_error,
    resolve_pageindex_key,
)
from .sec_markdown import load_company_section_docs, materialize_markdown_docs


COMPANY_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "plc",
    "group",
    "holdings",
}


def _normalize_text(value: str) -> str:
    """Normalize text for light-weight fuzzy matching."""
    value = value.lower().replace("'s", "")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _company_keywords(company_name: str) -> List[str]:
    """Build company keyword list without legal suffixes."""
    tokens = [tok for tok in _normalize_text(company_name).split() if tok and tok not in COMPANY_SUFFIXES]
    keywords: List[str] = []
    if tokens:
        keywords.append(" ".join(tokens))
        keywords.extend([tok for tok in tokens if len(tok) >= 4])
    # Stable de-dup preserving order.
    deduped: List[str] = []
    for word in keywords:
        if word not in deduped:
            deduped.append(word)
    return deduped


def infer_question_tickers(question: str, company_docs: List[Any]) -> List[str]:
    """Infer explicit ticker/company mentions from question text."""
    q_norm = _normalize_text(question)
    q_terms = set(q_norm.split())
    found: List[str] = []
    for doc in company_docs:
        ticker = str(getattr(doc, "ticker", "")).strip()
        company = str(getattr(doc, "company_name", "")).strip()
        if not ticker:
            continue
        ticker_hit = bool(re.search(rf"\b{re.escape(ticker.lower())}\b", q_norm))
        company_hit = False
        for keyword in _company_keywords(company):
            parts = keyword.split()
            if len(parts) == 1:
                company_hit = parts[0] in q_terms
            else:
                company_hit = keyword in q_norm
            if company_hit:
                break
        if ticker_hit or company_hit:
            found.append(ticker)
    deduped: List[str] = []
    for t in found:
        if t not in deduped:
            deduped.append(t)
    return deduped


def index_documents(
    client: Any,
    markdown_registry: List[Dict[str, str]],
    reindex: bool,
    index_mode: str,
) -> List[Dict[str, Any]]:
    """Index docs and return ticker/doc_id mapping."""
    indexed: List[Dict[str, Any]] = []
    existing_by_path: Dict[Path, str] = {}
    for doc_id, meta in client.documents.items():
        path_str = meta.get("path")
        if path_str:
            existing_by_path[Path(path_str).resolve()] = doc_id

    for row in markdown_registry:
        md_path = Path(row["markdown_path"]).resolve()
        ticker = row["ticker"]
        company_name = row.get("company_name", "")
        if (not reindex) and (md_path in existing_by_path):
            doc_id = existing_by_path[md_path]
            indexed.append(
                {
                    "ticker": ticker,
                    "company_name": company_name,
                    "accession_number": row.get("accession_number", ""),
                    "filing_date": row.get("filing_date", ""),
                    "filing_document_url": row.get("filing_document_url", ""),
                    "doc_id": doc_id,
                    "indexed_now": False,
                    "markdown_path": str(md_path),
                }
            )
            continue

        doc_id = client.index(str(md_path), mode=index_mode)
        indexed.append(
            {
                "ticker": ticker,
                "company_name": company_name,
                "accession_number": row.get("accession_number", ""),
                "filing_date": row.get("filing_date", ""),
                "filing_document_url": row.get("filing_document_url", ""),
                "doc_id": doc_id,
                "indexed_now": True,
                "markdown_path": str(md_path),
            }
        )

    return indexed


def _pageindex_chat_messages(question: str) -> List[Dict[str, str]]:
    """Build the prompt sent directly to PageIndex Chat."""
    return [
        {
            "role": "user",
            "content": (
                "Answer this question using only the indexed SEC 10-K documents. "
                "Use a plain-text terminal-friendly structure with these sections exactly: "
                "Question, Answer, Evidence, Sources. "
                "In Answer, use concise bullets when appropriate. "
                "In Evidence, summarize the most relevant cited findings. "
                "In Sources, list only citations present in the answer. "
                "Question: "
                f"{question}"
            ),
        },
    ]


def _extract_inline_citations(answer: str) -> List[str]:
    """Extract inline PageIndex citation markers from the answer text."""
    return list(dict.fromkeys(re.findall(r"<doc=[^>]+>", answer)))


def _extract_visible_answer(text: str) -> str:
    """Drop PageIndex planning/tool traces and keep only the rendered answer block."""
    if not text:
        return ""
    markers = ["**Question**", "Question:"]
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            return text[idx:].strip()
    return text.strip()


def _find_visible_answer_start(text: str) -> int | None:
    """Locate where the actual rendered answer begins in streamed content."""
    markers = ["**Question**", "Question:"]
    hits = [text.find(marker) for marker in markers if text.find(marker) >= 0]
    return min(hits) if hits else None


def _wait_for_documents_ready(
    client: Any,
    *,
    doc_ids: List[str],
    max_wait_sec: int = 180,
    poll_interval_sec: float = 3.0,
) -> List[Dict[str, Any]]:
    """Poll PageIndex until all indexed documents are ready for retrieval."""
    start = time.time()
    last_metadata: List[Dict[str, Any]] = []
    while True:
        last_metadata = []
        all_ready = True
        for doc_id in doc_ids:
            metadata = client.get_document(doc_id)
            last_metadata.append(metadata if isinstance(metadata, dict) else {"id": doc_id})
            status = str((metadata or {}).get("status", "")).strip().lower()
            ready = bool(client.is_retrieval_ready(doc_id))
            if status != "completed" or not ready:
                all_ready = False
        if all_ready:
            return last_metadata
        if time.time() - start >= max_wait_sec:
            raise RuntimeError(
                "PageIndex document processing is not complete yet. "
                "Please retry in a few minutes after the cloud index finishes."
            )
        time.sleep(poll_interval_sec)


def _run_pageindex_chat(
    client: Any,
    *,
    question: str,
    doc_ids: List[str],
    stream_handler: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Run native PageIndex chat over the selected documents."""
    answer_parts: List[str] = []
    raw_citation_events: List[Dict[str, Any]] = []
    visible_started = False
    visible_buffer = ""
    stream = client.chat_completions(
        messages=_pageindex_chat_messages(question),
        doc_id=doc_ids,
        stream=True,
        stream_metadata=True,
        enable_citations=True,
    )
    for chunk in stream:
        if not isinstance(chunk, dict):
            continue
        if str(chunk.get("object", "")).strip() == "chat.completion.citations":
            raw_citation_events.append(chunk)
            continue
        choices = chunk.get("choices", [])
        if not isinstance(choices, list) or not choices:
            continue
        delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
        content = delta.get("content", "")
        if not isinstance(content, str) or content == "":
            continue
        answer_parts.append(content)
        if stream_handler is not None:
            if visible_started:
                stream_handler(content)
            else:
                visible_buffer += content
                start_idx = _find_visible_answer_start(visible_buffer)
                if start_idx is not None:
                    visible_started = True
                    stream_handler(visible_buffer[start_idx:])

    answer = _extract_visible_answer("".join(answer_parts))
    if stream_handler is not None and not visible_started and answer:
        stream_handler(answer)
    return {
        "answer": answer,
        "inline_citations": _extract_inline_citations(answer),
        "raw_citation_events": raw_citation_events,
    }


def run_pipeline(
    sections_json_path: Path,
    docs_dir: Path,
    workspace: Path,
    output_dir: Path,
    question: Optional[str],
    openai_model: str,
    index_model: Optional[str],
    retrieve_model: Optional[str],
    reindex: bool,
    docs_only: bool,
    max_context_chars: int,
    index_mode: str,
    max_docs: int,
    max_depth: int,
    max_nodes_per_level: int,
    max_candidate_nodes: int,
    stream_handler: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Run complete pipeline and persist result artifacts."""
    load_dotenv()
    app_config = load_app_config()
    pageindex_key = app_config.pageindex_api_key

    company_docs = load_company_section_docs(sections_json_path)
    markdown_registry = materialize_markdown_docs(company_docs, docs_dir)
    write_json(output_dir / "markdown_registry.json", markdown_registry)

    if docs_only:
        summary = {
            "mode": "docs_only",
            "companies": len(company_docs),
            "markdown_docs": len(markdown_registry),
            "docs_dir": str(docs_dir.resolve()),
            "workspace": str(workspace.resolve()),
            "output_dir": str(output_dir.resolve()),
        }
        write_json(output_dir / "run_summary.json", summary)
        return summary

    pageindex_key = resolve_pageindex_key(pageindex_key)

    client = init_pageindex_client(
        workspace=workspace,
        pageindex_api_key=pageindex_key,
        index_model=index_model,
        retrieve_model=retrieve_model,
    )

    # If question explicitly targets a company and reindex is off, index only that subset.
    registry_for_index = markdown_registry
    if question and not reindex:
        inferred = infer_question_tickers(question, company_docs)
        if inferred:
            inferred_set = set(inferred)
            registry_for_index = [row for row in markdown_registry if row["ticker"] in inferred_set]

    adapter_mode = "cloud"
    try:
        indexed_docs = index_documents(client, registry_for_index, reindex=reindex, index_mode=index_mode)
    except Exception as exc:  # noqa: BLE001
        if not (is_pageindex_limit_error(exc) or is_pageindex_cloud_unavailable_error(exc)):
            raise
        raise RuntimeError(describe_pageindex_cloud_error(exc)) from exc
    write_json(output_dir / "doc_registry.json", indexed_docs)

    qa_result = None
    if question:
        docs_meta = [
            {
                "ticker": row["ticker"],
                "company_name": row.get("company_name", ""),
                "accession_number": row.get("accession_number", ""),
                "doc_id": row["doc_id"],
                "filing_date": row.get("filing_date", ""),
                "filing_document_url": row.get("filing_document_url", ""),
                "markdown_path": row.get("markdown_path", ""),
            }
            for row in indexed_docs
        ]
        document_status = _wait_for_documents_ready(
            client,
            doc_ids=[row["doc_id"] for row in indexed_docs],
        )
        chat_result = _run_pageindex_chat(
            client,
            question=question,
            doc_ids=[row["doc_id"] for row in indexed_docs],
            stream_handler=stream_handler,
        )
        qa_result = {
            "question": question,
            "adapter_mode": adapter_mode,
            "chat_mode": "pageindex_cloud_chat",
            "documents": docs_meta,
            "doc_ids": [row["doc_id"] for row in indexed_docs],
            "document_status": document_status,
            "answer": chat_result["answer"],
            "citations": chat_result["inline_citations"],
            "citation_events": chat_result["raw_citation_events"],
        }
        write_json(output_dir / "qa_result.json", qa_result)

    summary = {
        "sections_json": str(sections_json_path.resolve()),
        "docs_dir": str(docs_dir.resolve()),
        "workspace": str(workspace.resolve()),
        "output_dir": str(output_dir.resolve()),
        "companies": len(company_docs),
        "indexed_documents": len(indexed_docs),
        "adapter_mode": adapter_mode,
        "question_provided": bool(question),
        "qa_result_file": str((output_dir / "qa_result.json").resolve()) if qa_result else None,
        "tree_search_mode": "recursive_levelwise",
        "doc_routing_stage": "enabled",
    }
    write_json(output_dir / "run_summary.json", summary)
    return summary


