"""Top-level orchestration for SEC -> PageIndex -> recursive tree-search pipeline."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from config import load_app_config
from .json_utils import parse_json_array, write_json
from .sdk_loader import init_pageindex_client, resolve_pageindex_key
from .sec_markdown import load_company_section_docs, materialize_markdown_docs
from .tree_search import (
    fallback_route_documents,
    gather_context_from_pageindex,
    llm_answer_from_context,
    llm_select_documents,
    recursive_tree_search,
)


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
                "doc_id": doc_id,
                "indexed_now": True,
                "markdown_path": str(md_path),
            }
        )

    return indexed


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
) -> Dict[str, Any]:
    """Run complete pipeline and persist result artifacts."""
    load_dotenv()
    app_config = load_app_config()
    openai_key = app_config.openai_api_key
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

    indexed_docs = index_documents(client, registry_for_index, reindex=reindex, index_mode=index_mode)
    write_json(output_dir / "doc_registry.json", indexed_docs)

    qa_result = None
    if question:
        if not openai_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM-based document routing/tree search/answer generation.")
        openai_client = OpenAI(api_key=openai_key)
        docs_meta = [
            {
                "ticker": row["ticker"],
                "company_name": row.get("company_name", ""),
                "doc_id": row["doc_id"],
                "filing_date": next((d.filing_date for d in company_docs if d.ticker == row["ticker"]), ""),
            }
            for row in indexed_docs
        ]

        routing = llm_select_documents(
            openai_client=openai_client,
            llm_model=openai_model,
            question=question,
            docs_meta=docs_meta,
            max_docs=max_docs,
        )
        selected_tickers = routing.get("selected_tickers", [])
        if not selected_tickers:
            selected_tickers = fallback_route_documents(question, docs_meta, max_docs=max_docs)

        selected_doc_rows = [row for row in indexed_docs if row["ticker"] in set(selected_tickers)]
        if not selected_doc_rows:
            selected_doc_rows = indexed_docs[:max_docs]

        per_doc_results: List[Dict[str, Any]] = []
        combined_context_blocks: List[str] = []
        per_doc_budget = max(1000, max_context_chars // max(len(selected_doc_rows), 1))

        for row in selected_doc_rows:
            ticker = row["ticker"]
            company_name = row.get("company_name", "")
            doc_id = row["doc_id"]

            structure_raw = client.get_document_structure(doc_id)
            tree = parse_json_array(structure_raw)
            trace: List[Dict[str, Any]] = []
            leaf_nodes = recursive_tree_search(
                openai_client=openai_client,
                llm_model=openai_model,
                question=question,
                ticker=ticker,
                company_name=company_name,
                nodes=tree,
                depth=0,
                max_depth=max_depth,
                max_nodes_per_level=max_nodes_per_level,
                max_candidate_nodes=max_candidate_nodes,
                trace=trace,
            )

            context, evidence = gather_context_from_pageindex(
                client=client,
                doc_id=doc_id,
                ticker=ticker,
                selected_nodes=leaf_nodes,
                max_chars=per_doc_budget,
            )
            if context:
                combined_context_blocks.append(f"=== {ticker} ({company_name}) ===\n{context}")

            per_doc_results.append(
                {
                    "ticker": ticker,
                    "company_name": company_name,
                    "doc_id": doc_id,
                    "leaf_node_ids": [n.get("node_id") for n in leaf_nodes],
                    "tree_search_trace": trace,
                    "evidence": evidence,
                    "retrieved_context_chars": len(context),
                }
            )

        final_context = "\n\n".join(combined_context_blocks)[:max_context_chars]
        answer = llm_answer_from_context(
            openai_client=openai_client,
            llm_model=openai_model,
            question=question,
            context=final_context,
        )
        qa_result = {
            "question": question,
            "routing": {
                "llm_routing": routing,
                "selected_tickers": [row["ticker"] for row in selected_doc_rows],
            },
            "answer": answer,
            "per_document": per_doc_results,
        }
        write_json(output_dir / "qa_result.json", qa_result)

    summary = {
        "sections_json": str(sections_json_path.resolve()),
        "docs_dir": str(docs_dir.resolve()),
        "workspace": str(workspace.resolve()),
        "output_dir": str(output_dir.resolve()),
        "companies": len(company_docs),
        "indexed_documents": len(indexed_docs),
        "question_provided": bool(question),
        "qa_result_file": str((output_dir / "qa_result.json").resolve()) if qa_result else None,
        "tree_search_mode": "recursive_levelwise",
        "doc_routing_stage": "enabled",
    }
    write_json(output_dir / "run_summary.json", summary)
    return summary
