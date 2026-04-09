"""SEC EDGAR client for minimal 10-K ingestion.

Current behavior:
- Looks up CIK by ticker.
- Pulls recent company submissions.
- Filters filings by form type and date range.
- Downloads only the primary filing document.
- Writes one summary file: `companies.json`.
- Stores downloaded filing files locally as `primary_document` (no `.html` suffix).

Notes:
- SEC requests require a descriptive User-Agent with contact email.
- Client enforces conservative rate limiting (<10 requests/second).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# SEC fair access: max 10 requests/sec. 0.12s/request is ~8.3 req/sec.
RATE_LIMIT_DELAY = 0.12


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
    documents: List[Dict] = field(default_factory=list)


class EdgarClient:
    """HTTP client for SEC ticker, submissions, and archives endpoints."""

    SUBMISSIONS_URL = "https://data.sec.gov/submissions"
    ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    def __init__(self, user_agent: str):
        """Initialize a session with SEC-compliant headers.

        Args:
            user_agent: Must contain an email address for SEC compliance.
        """
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
        """Sleep if needed to keep request rate below SEC max."""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """Perform one rate-limited GET request.

        Raises:
            requests.exceptions.HTTPError: If SEC returns non-2xx.
        """
        self._rate_limit()
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    def get_cik(self, ticker: str) -> str:
        """Resolve a ticker symbol to zero-padded 10-digit CIK."""
        resp = self._get(self.TICKERS_URL)
        data = resp.json()

        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik = str(entry["cik_str"]).zfill(10)
                logger.info("Resolved %s -> CIK %s (%s)", ticker, cik, entry.get("title", ""))
                return cik

        raise ValueError(f"Ticker '{ticker}' not found in SEC EDGAR")

    def get_company_info(self, cik: str) -> Dict:
        """Fetch raw company submissions JSON for a CIK."""
        url = f"{self.SUBMISSIONS_URL}/CIK{cik}.json"
        resp = self._get(url)
        return resp.json()

    def get_filings(
        self,
        cik: str,
        filing_type: str = "10-K",
        count: int = 5,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Filing]:
        """Return recent filings filtered by form type and date bounds.

        The SEC submissions feed is already newest-first; this method preserves
        that order and stops when `count` filings are collected.
        """
        company_data = self.get_company_info(cik)
        company_name = company_data.get("name", "Unknown")

        recent = company_data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        periods = recent.get("reportDate", [])
        items_list = recent.get("items", [])

        filings: List[Filing] = []
        for i, form in enumerate(forms):
            if form != filing_type:
                continue

            filing_date = dates[i] if i < len(dates) else ""

            # ISO date string comparison is safe for YYYY-MM-DD format.
            if start_date and filing_date < start_date:
                continue
            if end_date and filing_date > end_date:
                continue

            filings.append(
                Filing(
                    accession_number=accessions[i] if i < len(accessions) else "",
                    filing_type=form,
                    filing_date=filing_date,
                    primary_document=primary_docs[i] if i < len(primary_docs) else "",
                    company_name=company_name,
                    cik=cik,
                    period_of_report=periods[i] if i < len(periods) else "",
                    items=items_list[i] if i < len(items_list) else "",
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
        """Build SEC archive URL for a filing's primary document."""
        accession_clean = filing.accession_number.replace("-", "")
        cik_clean = filing.cik.lstrip("0")
        return f"{self.ARCHIVES_URL}/{cik_clean}/{accession_clean}/{filing.primary_document}"

    def download_filing(self, filing: Filing) -> str:
        """Download and return primary filing document content."""
        url = self.filing_document_url(filing)
        logger.info("Downloading %s from %s", filing.filing_type, url)
        resp = self._get(url)
        return resp.text

    
    def ingest_company(
        self,
        ticker: str,
        data_dir: str = "data_edgarfolder",
        filing_type: str = "10-K",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_filings: int = 3,
    ) -> Dict:
        """Ingest one company's filings and save local primary documents.

        Writes documents to:
        `{data_dir}/{TICKER}/{ACCESSION}/primary_document`

        Returns a summary dict used to build `companies.json`.
        """
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

        saved_filings: List[Dict] = []
        for filing in filings:
            accession_clean = filing.accession_number.replace("-", "")
            filing_dir = company_dir / accession_clean
            filing_dir.mkdir(parents=True, exist_ok=True)

            filing_record: Dict = {
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
            "downloaded_filings": sum(1 for f in saved_filings if f.get("primary_document_saved")),
            "company_dir": str(company_dir.resolve()),
            "filings": saved_filings,
        }


def run_batch_ingestion(
    user_agent: str,
    tickers: List[str],
    data_dir: str = "Ingestion\\Sec_Edgar10kfillings\\data_edgarfolder",
    filing_type: str = "10-K",
    max_filings_per_ticker: int = 2,
) -> List[Dict]:
    """Run one-year batch ingestion and write `companies.json`.

    Output file:
        `{data_dir}/companies.json`

    Each companies.json row includes ticker, company_name, cik, filing_date,
    SEC filing URL, local file path, and downloaded flag.
    """
    client = EdgarClient(user_agent=user_agent)

    # Use rolling one-year window ending today (UTC date).
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=365)

    results: List[Dict] = []
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
            logger.info(
                "Ingested %s: retrieved=%s saved=%s",
                ticker,
                summary["retrieved_filings"],
                summary["downloaded_filings"],
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

    companies_minimal: List[Dict] = []
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

    companies_path = Path(data_dir) / "companies.json"
    companies_path.parent.mkdir(parents=True, exist_ok=True)
    companies_path.write_text(json.dumps(companies_minimal, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    """Script entrypoint for local manual execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # Fixed 3-company run as requested.
    tickers = ["AAPL", "MSFT", "NVDA"]

    # Replace with your real contact email.
    user_agent = "SupplyChainNexus/1.0 contact@example.com"

    batch_results = run_batch_ingestion(
        user_agent=user_agent,
        tickers=tickers,
        data_dir="Ingestion\\Sec_Edgar10kfillings\\data_edgarfolder",
        filing_type="10-K",
        max_filings_per_ticker=1,
    )

    ok = sum(1 for r in batch_results if r.get("status") != "error")
    failed = len(batch_results) - ok

    print(
        json.dumps(
            {
                "status": "completed",
                "tickers_total": len(batch_results),
                "tickers_ok": ok,
                "tickers_failed": failed,
                "output_dir": str(Path("Ingestion\\Sec_Edgar10kfillings\\data_edgarfolder").resolve()),
            },
            indent=2,
        )
    )
