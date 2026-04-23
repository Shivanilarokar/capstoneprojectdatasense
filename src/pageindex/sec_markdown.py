"""SEC section normalization and markdown tree-shaping for PageIndex."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from .models import CompanySectionDoc

NOTES_HEADER_RE = re.compile(
    r"(?im)\bnotes?\s+to\s+(?:the\s+)?(?:consolidated\s+)?financial\s+statements?\b"
)
ITEM_HEADER_RE = re.compile(r"(?im)^\s*item\s+(1a|1|7a|7|8|16)\b")
NUMBERED_HEADING_RE = re.compile(
    r"^(?:\(?\d{1,2}[a-z]?\)|\d{1,2}[.)]|[a-z][.)]|[ivxlcdm]{1,8}[.)])\s+.+$",
    re.IGNORECASE,
)
TITLE_CASE_COLON_RE = re.compile(r"^[A-Z][A-Za-z0-9,\-()/&' ]{2,120}:$")
TITLE_CASE_LINE_RE = re.compile(r"^[A-Z][A-Za-z&'()/\-]*(?:\s+[A-Z][A-Za-z&'()/\-]*){1,11}$")
RISK_STYLE_RE = re.compile(
    r"(?i)^(risk related to|we depend on|we rely on|our business is subject to|our operations are subject to|single source|supply chain|supplier|geopolitical|commodity|inventory|manufacturing)\b"
)


def extract_notes_from_item8(item8_text: str) -> str:
    """Extract Notes to Financial Statements subsection from Item 8."""
    if not item8_text:
        return ""
    match = NOTES_HEADER_RE.search(item8_text)
    if not match:
        return ""
    return item8_text[match.start() :].strip()


def clip_section_by_next_items(section_text: str, next_items: Sequence[str]) -> str:
    """Clip item text at earliest likely next item marker to avoid bleed-over."""
    if not section_text.strip():
        return ""

    lower_text = section_text.lower()
    cut_at = len(section_text)
    for nxt in next_items:
        pattern = re.compile(rf"(?im)^\s*item\s+{re.escape(nxt.lower())}\b")
        match = pattern.search(lower_text)
        if match:
            cut_at = min(cut_at, match.start())
    return section_text[:cut_at].strip()


def load_company_section_docs(sections_json_path: Path) -> List[CompanySectionDoc]:
    """Load extracted section JSON and normalize each SEC item block."""
    rows = json.loads(sections_json_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected list in {sections_json_path}, got {type(rows).__name__}.")

    docs: List[CompanySectionDoc] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        sections = row.get("sections", {}) if isinstance(row.get("sections"), dict) else {}
        item1_raw = sections.get("item1", "") or ""
        item1a_raw = sections.get("item1a", "") or ""
        item7_raw = sections.get("item7", "") or ""
        item7a_raw = sections.get("item7a", "") or ""
        item8_raw = sections.get("item8", "") or ""
        item16_raw = sections.get("item16", "") or ""

        item1 = clip_section_by_next_items(item1_raw, ["1a", "1b", "1c", "2"])
        item1a = clip_section_by_next_items(item1a_raw, ["1b", "1c", "2", "3"])
        item7 = clip_section_by_next_items(item7_raw, ["7a", "8", "9"])
        item7a = clip_section_by_next_items(item7a_raw, ["8", "9"])
        item8 = clip_section_by_next_items(item8_raw, ["9", "10", "15", "16"])
        item16 = clip_section_by_next_items(item16_raw, ["signature"])

        docs.append(
            CompanySectionDoc(
                ticker=row.get("ticker", ""),
                company_name=row.get("company_name", ""),
                cik=row.get("cik", ""),
                filing_date=row.get("filing_date", ""),
                filing_document_url=row.get("filing_document_url", ""),
                item1=item1,
                item1a=item1a,
                item7=item7,
                item7a=item7a,
                item8=item8,
                item16=item16,
                notes=extract_notes_from_item8(item8),
            )
        )
    return docs


def normalize_heading_text(text: str) -> str:
    """Normalize heading candidate text."""
    clean = re.sub(r"\s+", " ", text.strip()).rstrip(":")
    if len(clean) > 140:
        clean = clean[:140].rstrip()
    return clean or "Subsection"


def is_likely_subheading(line: str) -> bool:
    """Heuristic subheading detector for SEC narrative lines."""
    candidate = line.strip()
    if not candidate or len(candidate) > 150:
        return False
    if ITEM_HEADER_RE.match(candidate):
        return False
    if re.match(r"(?i)^table of contents$", candidate):
        return False
    if re.match(r"(?i)^part\s+[ivx]+$", candidate):
        return False

    if NUMBERED_HEADING_RE.match(candidate):
        return True
    if TITLE_CASE_COLON_RE.match(candidate):
        return True
    if TITLE_CASE_LINE_RE.match(candidate) and not any(ch.isdigit() for ch in candidate):
        return 2 <= len(candidate.split()) <= 10
    if RISK_STYLE_RE.match(candidate):
        return True

    letters = [c for c in candidate if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= 0.85 and 3 <= len(candidate.split()) <= 14:
            return True
    return False


def split_item_into_subsections(item_text: str, fallback_title: str) -> List[Tuple[str, str]]:
    """Split one item block into subsection pairs (title, body)."""
    if not item_text.strip():
        return []

    lines = item_text.splitlines()
    sections: List[Tuple[str, str]] = []
    current_title = fallback_title
    current_buffer: List[str] = []

    def flush() -> None:
        nonlocal current_buffer
        body = "\n".join(current_buffer).strip()
        if body:
            sections.append((current_title, body))
        current_buffer = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            if current_buffer and current_buffer[-1] != "":
                current_buffer.append("")
            continue
        if is_likely_subheading(stripped):
            flush()
            current_title = normalize_heading_text(stripped)
            continue
        current_buffer.append(stripped)

    flush()
    if not sections:
        return [(fallback_title, item_text.strip())]

    merged: List[Tuple[str, str]] = []
    for title, body in sections:
        if merged and len(body) < 180:
            prev_title, prev_body = merged[-1]
            merged[-1] = (prev_title, f"{prev_body}\n\n{title}\n{body}".strip())
        else:
            merged.append((title, body))
    return merged


def append_item_block(lines: List[str], item_heading: str, item_text: str, fallback_subtitle: str) -> None:
    """Append one item section with subsection headings."""
    lines.append(f"## {item_heading}")
    if not item_text.strip():
        lines.append("[NOT FOUND]")
        lines.append("")
        return

    seen_titles: Dict[str, int] = {}
    for title, body in split_item_into_subsections(item_text, fallback_title=fallback_subtitle):
        count = seen_titles.get(title, 0) + 1
        seen_titles[title] = count
        unique_title = f"{title} ({count})" if count > 1 else title
        lines.append(f"### {unique_title}")
        lines.append(body)
        lines.append("")


def build_markdown_for_company(doc: CompanySectionDoc) -> str:
    """Build markdown with deeper hierarchy for PageIndex tree quality."""
    lines: List[str] = [
        f"# {doc.ticker} 10-K Supply Chain File",
        "",
        "## Filing Metadata",
        f"- Ticker: {doc.ticker}",
        f"- Company: {doc.company_name}",
        f"- CIK: {doc.cik}",
        f"- Filing Date: {doc.filing_date}",
        f"- SEC URL: {doc.filing_document_url}",
        "",
    ]
    append_item_block(lines, "Item 1 - Business", doc.item1, "Business Overview")
    append_item_block(lines, "Item 1A - Risk Factors", doc.item1a, "Risk Factors")
    append_item_block(lines, "Item 7 - MD&A", doc.item7, "Management Discussion and Analysis")
    append_item_block(
        lines,
        "Item 7A - Quantitative and Qualitative Disclosures About Market Risk",
        doc.item7a,
        "Market Risk Disclosures",
    )
    append_item_block(
        lines,
        "Item 8 - Financial Statements and Supplementary Data",
        doc.item8,
        "Financial Statements and Supplementary Data",
    )
    append_item_block(lines, "Notes to Financial Statements", doc.notes, "Notes to Financial Statements")
    append_item_block(lines, "Item 16 - Form 10-K Summary", doc.item16, "Form 10-K Summary")
    return "\n".join(lines).strip() + "\n"


def materialize_markdown_docs(docs: List[CompanySectionDoc], docs_dir: Path) -> List[Dict[str, str]]:
    """Write markdown files and return registry."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    registry: List[Dict[str, str]] = []
    for doc in docs:
        md_path = docs_dir / f"{doc.ticker}_10k_supply_chain.md"
        md_path.write_text(build_markdown_for_company(doc), encoding="utf-8")
        registry.append(
            {
                "ticker": doc.ticker,
                "company_name": doc.company_name,
                "markdown_path": str(md_path.resolve()),
            }
        )
    return registry

