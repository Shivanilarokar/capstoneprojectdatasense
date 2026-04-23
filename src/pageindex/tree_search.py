"""Document routing, recursive tree search, and evidence extraction."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from openai import OpenAI

from .json_utils import parse_json_array
from .llm import chat_json, chat_text

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


def extract_query_terms(question: str) -> Set[str]:
    """Extract lightweight keyword set for lexical fallback ranking."""
    tokens = re.findall(r"[A-Za-z0-9]{3,}", question.lower())
    return {t for t in tokens if t not in STOPWORDS}


def rank_nodes_for_question(question: str, nodes: Sequence[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Lexical pre-rank nodes to cap prompt size at each depth."""
    q_terms = extract_query_terms(question)
    if not q_terms:
        return list(nodes)[:limit]

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for node in nodes:
        title = str(node.get("title", "")).lower()
        summary = str(node.get("summary", "") or node.get("prefix_summary", "")).lower()
        text = f"{title} {summary}"
        overlap = sum(1 for t in q_terms if t in text)
        if node.get("nodes"):
            overlap += 1
        scored.append((overlap, node))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for s, n in scored if s > 0][:limit] or list(nodes)[:limit]


def compact_node_for_prompt(node: Dict[str, Any], max_summary_chars: int = 280) -> Dict[str, Any]:
    """Keep only fields required by tree-search reasoning prompts."""
    out: Dict[str, Any] = {
        "node_id": node.get("node_id"),
        "title": node.get("title"),
        "has_children": bool(node.get("nodes")),
    }
    summary = node.get("summary") or node.get("prefix_summary") or ""
    if isinstance(summary, str) and summary:
        out["summary"] = summary[:max_summary_chars]
    if "line_num" in node:
        out["line_num"] = node.get("line_num")
    if "page_index" in node:
        out["page_index"] = node.get("page_index")
    if "start_index" in node:
        out["start_index"] = node.get("start_index")
    if "end_index" in node:
        out["end_index"] = node.get("end_index")
    return out


def llm_select_documents(
    openai_client: OpenAI,
    llm_model: str,
    question: str,
    docs_meta: List[Dict[str, Any]],
    max_docs: int,
) -> Dict[str, Any]:
    """Stage-1 route: choose relevant company docs before tree traversal."""
    prompt = f"""
You are routing a question to the most relevant SEC 10-K company documents.

Question:
{question}

Candidate documents:
{json.dumps(docs_meta, indent=2)}

Rules:
1) Select up to {max_docs} ticker(s) that are most relevant.
2) If question explicitly names a company/ticker, prioritize that exact match.
3) If question is broad/comparative, select multiple docs.
4) Return strict JSON only.

JSON schema:
{{
  "thinking": "short reason",
  "selected_tickers": ["AAPL", "MSFT"]
}}
"""
    parsed = chat_json(openai_client, llm_model, prompt, temperature=0)
    tickers = parsed.get("selected_tickers", [])
    if not isinstance(tickers, list):
        tickers = []
    parsed["selected_tickers"] = [t for t in tickers if isinstance(t, str)][:max_docs]
    return parsed


def fallback_route_documents(question: str, docs_meta: List[Dict[str, Any]], max_docs: int) -> List[str]:
    """Deterministic fallback when router output is missing."""
    q = question.lower()
    selected: List[str] = []
    for doc in docs_meta:
        ticker = str(doc.get("ticker", "")).lower()
        company = str(doc.get("company_name", "")).lower()
        if ticker and re.search(rf"\b{re.escape(ticker)}\b", q):
            selected.append(doc["ticker"])
            continue
        if company and company in q:
            selected.append(doc["ticker"])

    deduped: List[str] = []
    for ticker in selected:
        if ticker not in deduped:
            deduped.append(ticker)
    if deduped:
        return deduped[:max_docs]
    return [d["ticker"] for d in docs_meta[:max_docs]]


def llm_select_nodes_for_level(
    openai_client: OpenAI,
    llm_model: str,
    question: str,
    ticker: str,
    company_name: str,
    depth: int,
    nodes_payload: List[Dict[str, Any]],
    max_select: int,
) -> Dict[str, Any]:
    """Pick relevant nodes from one tree depth level."""
    prompt = f"""
You are performing PageIndex tree search on SEC 10-K structure.
Company: {company_name} ({ticker})
Tree depth level: {depth}

Question:
{question}

Nodes at this level:
{json.dumps(nodes_payload, indent=2)}

Select up to {max_select} node ids likely to contain the answer.
Prefer precise, specific nodes. If nothing is relevant, return an empty list.

Return strict JSON only:
{{
  "thinking": "short reason",
  "node_list": ["0003", "0009"]
}}
"""
    parsed = chat_json(openai_client, llm_model, prompt, temperature=0)
    node_list = parsed.get("node_list", [])
    if not isinstance(node_list, list):
        node_list = []
    parsed["node_list"] = [node for node in node_list if isinstance(node, str)][:max_select]
    return parsed


def recursive_tree_search(
    openai_client: OpenAI,
    llm_model: str,
    question: str,
    ticker: str,
    company_name: str,
    nodes: List[Dict[str, Any]],
    depth: int,
    max_depth: int,
    max_nodes_per_level: int,
    max_candidate_nodes: int,
    trace: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Stage-2 recursive tree search (coarse -> fine)."""
    if not nodes or depth >= max_depth:
        return []

    candidates = rank_nodes_for_question(question, nodes, limit=max_candidate_nodes)
    payload = [compact_node_for_prompt(n) for n in candidates]
    selection = llm_select_nodes_for_level(
        openai_client=openai_client,
        llm_model=llm_model,
        question=question,
        ticker=ticker,
        company_name=company_name,
        depth=depth,
        nodes_payload=payload,
        max_select=max_nodes_per_level,
    )

    selected_ids = selection.get("node_list", [])
    selected_nodes = [n for n in candidates if n.get("node_id") in set(selected_ids)]
    fallback_used = False
    if not selected_nodes and candidates:
        selected_nodes = [candidates[0]]
        fallback_used = True

    trace.append(
        {
            "depth": depth,
            "candidate_node_ids": [n.get("node_id") for n in candidates],
            "selected_node_ids": [n.get("node_id") for n in selected_nodes],
            "llm_thinking": selection.get("thinking", ""),
            "fallback_used": fallback_used,
        }
    )

    leaves: List[Dict[str, Any]] = []
    for node in selected_nodes:
        children = node.get("nodes") or []
        if children and (depth + 1) < max_depth:
            child_leaves = recursive_tree_search(
                openai_client=openai_client,
                llm_model=llm_model,
                question=question,
                ticker=ticker,
                company_name=company_name,
                nodes=children,
                depth=depth + 1,
                max_depth=max_depth,
                max_nodes_per_level=max_nodes_per_level,
                max_candidate_nodes=max_candidate_nodes,
                trace=trace,
            )
            leaves.extend(child_leaves or [node])
        else:
            leaves.append(node)

    deduped: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for node in leaves:
        node_id = str(node.get("node_id", ""))
        if node_id and node_id not in seen:
            seen.add(node_id)
            deduped.append(node)
    return deduped


def page_selector_for_node(node: Dict[str, Any]) -> Optional[str]:
    """Convert selected node metadata to PageIndex get_page_content selector."""
    page_index = node.get("page_index")
    if isinstance(page_index, int) and page_index > 0:
        return str(page_index)

    line_num = node.get("line_num")
    if isinstance(line_num, int) and line_num > 0:
        return str(line_num)
    start_idx = node.get("start_index")
    end_idx = node.get("end_index")
    if isinstance(start_idx, int):
        start = max(1, start_idx)
        if isinstance(end_idx, int) and end_idx >= start:
            return f"{start}-{end_idx}"
        return str(start)
    return None


def gather_context_from_pageindex(
    client: Any,
    doc_id: str,
    ticker: str,
    selected_nodes: List[Dict[str, Any]],
    max_chars: int,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Fetch node-grounded evidence via PageIndex get_page_content."""
    blocks: List[str] = []
    used = 0
    evidence_meta: List[Dict[str, Any]] = []
    seen_selectors: Set[str] = set()

    for node in selected_nodes:
        node_id = str(node.get("node_id", ""))
        title = str(node.get("title", ""))
        selector = page_selector_for_node(node)
        if not selector or selector in seen_selectors:
            continue
        seen_selectors.add(selector)

        raw = client.get_page_content(doc_id, selector)
        page_rows = parse_json_array(raw)
        if not page_rows:
            continue

        joined_parts: List[str] = []
        page_ids: List[Any] = []
        for row in page_rows:
            if not isinstance(row, dict):
                continue
            page_ids.append(row.get("page"))
            content = str(row.get("content", "")).strip()
            if content:
                joined_parts.append(content)
        joined_text = "\n\n".join(joined_parts).strip()
        if not joined_text:
            continue

        block = f"[{ticker}:{node_id}] {title}\n{joined_text}\n"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining <= 0:
                break
            block = block[:remaining]
        blocks.append(block)
        used += len(block)
        evidence_meta.append(
            {
                "node_id": node_id,
                "title": title,
                "selector": selector,
                "pages_or_lines": page_ids,
            }
        )
        if used >= max_chars:
            break

    return "\n".join(blocks).strip(), evidence_meta


def llm_answer_from_context(openai_client: OpenAI, llm_model: str, question: str, context: str) -> str:
    """Generate grounded final answer from retrieved context only."""
    prompt = f"""
Answer the question using only the provided context.
If the context is insufficient, explicitly say "Insufficient evidence in retrieved context."

Question:
{question}

Context:
{context}
"""
    return chat_text(openai_client, llm_model, prompt, temperature=0)
