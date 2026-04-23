"""SEC EDGAR ingestion and 10-K section extraction utilities."""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 0.12
DEFAULT_SEC_DATA_DIR = "data/ingestion/sec/edgar"
DEFAULT_COMPANIES_JSON = "data/ingestion/sec/companies.json"
DEFAULT_EXTRACTED_SECTIONS_JSON = "data/ingestion/sec/extracted_10k_sections.json"

ITEM_ORDER = ["1", "1a", "7", "7a", "8", "16"]
ITEM_KEY = {
    "1": "item1",
    "1a": "item1a",
    "7": "item7",
    "7a": "item7a",
    "8": "item8",
    "16": "item16",
}
GENERIC_ITEM_PATTERN = re.compile(r"(?im)^\s*item\s+(1a|1|7a|7|8|16)\b")
TITLE_PATTERNS = {
    "1": re.compile(r"(?im)^\s*item\s+1\b[^\n]{0,180}\bbusiness\b"),
    "1a": re.compile(r"(?im)^\s*item\s+1a\b[^\n]{0,220}\brisk\s+factors?\b"),
    "7": re.compile(r"(?im)^\s*item\s+7\b[^\n]{0,260}\b(management|discussion|analysis|md&a)\b"),
    "7a": re.compile(r"(?im)^\s*item\s+7a\b[^\n]{0,260}\b(quantitative|qualitative|market\s+risk)\b"),
    "8": re.compile(r"(?im)^\s*item\s+8\b[^\n]{0,260}\b(financial\s+statements?|supplementary)\b"),
    "16": re.compile(r"(?im)^\s*item\s+16\b"),
}


@dataclass
class Filing:
    """Normalized filing record used across the ingestion pipeline."""

    accession_number: str
    filing_type: str
    filing_date: str
    primary_document: str
    company_name: str
    cik: str
    period_of_report: str = ""
    items: str = ""
    documents: list[dict[str, Any]] = field(default_factory=list)


class EdgarClient:
    """HTTP client for SEC ticker, submissions, and archives endpoints."""

    SUBMISSIONS_URL = "https://data.sec.gov/submissions"
    ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    def __init__(self, user_agent: str):
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC requires a User-Agent with contact email. "
                "Format: 'AppName contact@example.com'"
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json, text/html, */*",
            }
        )
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        self._rate_limit()
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    def get_cik(self, ticker: str) -> str:
        response = self._get(self.TICKERS_URL)
        data = response.json()

        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik = str(entry["cik_str"]).zfill(10)
                logger.info("Resolved %s -> CIK %s (%s)", ticker, cik, entry.get("title", ""))
                return cik

        raise ValueError(f"Ticker '{ticker}' not found in SEC EDGAR")

    def get_company_info(self, cik: str) -> dict[str, Any]:
        response = self._get(f"{self.SUBMISSIONS_URL}/CIK{cik}.json")
        return response.json()

    def get_filings(
        self,
        cik: str,
        filing_type: str = "10-K",
        count: int = 5,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Filing]:
        company_data = self.get_company_info(cik)
        company_name = company_data.get("name", "Unknown")

        recent = company_data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        periods = recent.get("reportDate", [])
        items_list = recent.get("items", [])

        filings: list[Filing] = []
        for index, form in enumerate(forms):
            if form != filing_type:
                continue

            filing_date = dates[index] if index < len(dates) else ""
            if start_date and filing_date < start_date:
                continue
            if end_date and filing_date > end_date:
                continue

            filings.append(
                Filing(
                    accession_number=accessions[index] if index < len(accessions) else "",
                    filing_type=form,
                    filing_date=filing_date,
                    primary_document=primary_docs[index] if index < len(primary_docs) else "",
                    company_name=company_name,
                    cik=cik,
                    period_of_report=periods[index] if index < len(periods) else "",
                    items=items_list[index] if index < len(items_list) else "",
                )
            )
            if len(filings) >= count:
                break

        logger.info(
            "Found %s %s filings for %s (CIK %s)",
            len(filings),
            filing_type,
            company_name,
            cik,
        )
        return filings

    def filing_document_url(self, filing: Filing) -> str:
        accession_clean = filing.accession_number.replace("-", "")
        cik_clean = filing.cik.lstrip("0")
        return f"{self.ARCHIVES_URL}/{cik_clean}/{accession_clean}/{filing.primary_document}"

    def download_filing(self, filing: Filing) -> str:
        response = self._get(self.filing_document_url(filing))
        return response.text

    def ingest_company(
        self,
        ticker: str,
        data_dir: str = DEFAULT_SEC_DATA_DIR,
        filing_type: str = "10-K",
        start_date: str | None = None,
        end_date: str | None = None,
        max_filings: int = 3,
    ) -> dict[str, Any]:
        ticker = ticker.upper()
        company_dir = Path(data_dir) / ticker
        company_dir.mkdir(parents=True, exist_ok=True)

        cik = self.get_cik(ticker)
        company_info = self.get_company_info(cik)
        company_name = company_info.get("name", "")

        filings = self.get_filings(
            cik=cik,
            filing_type=filing_type,
            count=max_filings,
            start_date=start_date,
            end_date=end_date,
        )

        saved_filings: list[dict[str, Any]] = []
        for filing in filings:
            accession_clean = filing.accession_number.replace("-", "")
            filing_dir = company_dir / accession_clean
            filing_dir.mkdir(parents=True, exist_ok=True)

            filing_record: dict[str, Any] = {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filing_date": filing.filing_date,
                "period_of_report": filing.period_of_report,
                "primary_document": filing.primary_document,
                "company_name": filing.company_name,
                "cik": filing.cik,
                "primary_document_saved": False,
                "filing_document_url": self.filing_document_url(filing),
                "errors": [],
            }

            try:
                html = self.download_filing(filing)
                doc_path = filing_dir / "primary_document"
                doc_path.write_text(html, encoding="utf-8")
                filing_record["primary_document_saved"] = True
                filing_record["primary_document_path"] = str(doc_path.resolve())
            except Exception as exc:  # noqa: BLE001
                filing_record["errors"].append(f"download_filing_error: {exc}")

            saved_filings.append(filing_record)

        return {
            "ticker": ticker,
            "company_name": company_name,
            "cik": cik,
            "filing_type": filing_type,
            "start_date": start_date,
            "end_date": end_date,
            "requested_max_filings": max_filings,
            "retrieved_filings": len(filings),
            "downloaded_filings": sum(1 for filing in saved_filings if filing.get("primary_document_saved")),
            "company_dir": str(company_dir.resolve()),
            "filings": saved_filings,
        }


def run_batch_ingestion(
    user_agent: str,
    tickers: list[str],
    data_dir: str = DEFAULT_SEC_DATA_DIR,
    companies_output_path: str | None = DEFAULT_COMPANIES_JSON,
    filing_type: str = "10-K",
    max_filings_per_ticker: int = 2,
) -> list[dict[str, Any]]:
    client = EdgarClient(user_agent=user_agent)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=365)

    results: list[dict[str, Any]] = []
    for ticker in tickers:
        try:
            summary = client.ingest_company(
                ticker=ticker,
                data_dir=data_dir,
                filing_type=filing_type,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                max_filings=max_filings_per_ticker,
            )
            results.append(summary)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed ingestion for %s", ticker)
            results.append(
                {
                    "ticker": ticker,
                    "status": "error",
                    "error": str(exc),
                    "filing_type": filing_type,
                    "data_dir": str(Path(data_dir).resolve()),
                }
            )

    companies_minimal: list[dict[str, Any]] = []
    for result in results:
        if result.get("status") == "error":
            companies_minimal.append(
                {
                    "ticker": result.get("ticker"),
                    "status": "error",
                    "error": result.get("error"),
                }
            )
            continue

        first_filing = result.get("filings", [{}])[0] if result.get("filings") else {}
        companies_minimal.append(
            {
                "ticker": result.get("ticker"),
                "company_name": result.get("company_name"),
                "cik": result.get("cik"),
                "filing_date": first_filing.get("filing_date"),
                "filing_document_url": first_filing.get("filing_document_url"),
                "local_document_path": first_filing.get("primary_document_path"),
                "downloaded": first_filing.get("primary_document_saved", False),
            }
        )

    companies_path = Path(companies_output_path) if companies_output_path else Path(data_dir).parent / "companies.json"
    companies_path.parent.mkdir(parents=True, exist_ok=True)
    companies_path.write_text(json.dumps(companies_minimal, indent=2), encoding="utf-8")
    return results


def _derive_local_document_path(company: dict[str, Any], companies_json: Path) -> Path | None:
    raw_value = str(company.get("local_document_path", "")).strip()
    if raw_value:
        raw_path = Path(raw_value)
        if raw_path.exists():
            return raw_path

    filing_url = str(company.get("filing_document_url", "")).strip()
    ticker = str(company.get("ticker", "")).strip().upper()
    if not filing_url or not ticker:
        return None

    url_parts = [part for part in filing_url.split("/") if part]
    if len(url_parts) < 2:
        return None

    accession = url_parts[-2]
    sec_root = companies_json.parent
    edgar_root = sec_root / "edgar" if (sec_root / "edgar").exists() else sec_root
    candidate = edgar_root / ticker / accession / "primary_document"
    if candidate.exists():
        return candidate
    return None


def html_to_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def collect_candidates(text: str) -> dict[str, list[tuple[int, int]]]:
    candidates: dict[str, list[tuple[int, int]]] = {item: [] for item in ITEM_ORDER}
    for item, pattern in TITLE_PATTERNS.items():
        for match in pattern.finditer(text):
            candidates[item].append((match.start(), 2))

    for match in GENERIC_ITEM_PATTERN.finditer(text):
        item = match.group(1).lower()
        candidates[item].append((match.start(), 1))

    output: dict[str, list[tuple[int, int]]] = {item: [] for item in ITEM_ORDER}
    for item in ITEM_ORDER:
        best_by_pos: dict[int, int] = {}
        for pos, score in candidates[item]:
            best_by_pos[pos] = max(best_by_pos.get(pos, 0), score)
        output[item] = sorted(best_by_pos.items(), key=lambda pair: pair[0])
    return output


def choose_starts(candidates: dict[str, list[tuple[int, int]]], text_len: int) -> dict[str, int]:
    starts: dict[str, int] = {}
    previous = -1
    toc_cutoff = int(text_len * 0.08)

    for item in ITEM_ORDER:
        options = [(position, score) for position, score in candidates.get(item, []) if position > previous]
        if not options:
            continue
        non_toc = [(position, score) for position, score in options if position > toc_cutoff]
        working = non_toc if non_toc else options
        chosen_pos, _score = sorted(working, key=lambda pair: (pair[1], pair[0]))[-1]
        starts[item] = chosen_pos
        previous = chosen_pos

    return starts


def extract_sections(text: str) -> dict[str, str]:
    candidates = collect_candidates(text)
    starts = choose_starts(candidates, len(text))
    sections = {ITEM_KEY[item]: "" for item in ITEM_ORDER}

    for index, item in enumerate(ITEM_ORDER):
        if item not in starts:
            continue

        start = starts[item]
        end = len(text)
        for next_item in ITEM_ORDER[index + 1 :]:
            if next_item in starts and starts[next_item] > start:
                end = starts[next_item]
                break

        sections[ITEM_KEY[item]] = text[start:end].strip()

    return sections


def extract_sections_from_companies(companies_json: Path, output_json: Path) -> dict[str, Any]:
    companies = json.loads(companies_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []

    for company in companies:
        if not company.get("downloaded"):
            continue

        source_path = _derive_local_document_path(company, companies_json)
        if source_path is None or not source_path.exists():
            rows.append(
                {
                    "ticker": company.get("ticker"),
                    "error": f"missing local filing file: {source_path}",
                }
            )
            continue

        raw_html = source_path.read_text(encoding="utf-8", errors="replace")
        text = html_to_text(raw_html)
        sections = extract_sections(text)
        rows.append(
            {
                "ticker": company.get("ticker"),
                "company_name": company.get("company_name"),
                "cik": company.get("cik"),
                "filing_date": company.get("filing_date"),
                "filing_document_url": company.get("filing_document_url"),
                "local_document_path": str(source_path.resolve()),
                "section_char_counts": {key: len(value) for key, value in sections.items()},
                "sections": sections,
            }
        )

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return {
        "companies_json": str(companies_json.resolve()),
        "output_json": str(output_json.resolve()),
        "companies_processed": len(rows),
    }


def parse_extract_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Item 1/1A/7/7A/8/16 from SEC filings.")
    parser.add_argument(
        "--companies-json",
        default=DEFAULT_COMPANIES_JSON,
        help="Path to companies.json",
    )
    parser.add_argument(
        "--output-json",
        default=DEFAULT_EXTRACTED_SECTIONS_JSON,
        help="Output JSON path",
    )
    return parser.parse_args(argv)


def main_extract_sections(argv: list[str] | None = None) -> None:
    args = parse_extract_args(argv)
    summary = extract_sections_from_companies(Path(args.companies_json), Path(args.output_json))
    print(json.dumps(summary, indent=2))

