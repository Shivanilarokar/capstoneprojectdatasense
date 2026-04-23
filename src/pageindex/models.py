"""Data models for SEC section ingestion and markdown materialization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompanySectionDoc:
    """In-memory representation of one company section document."""

    ticker: str
    company_name: str
    cik: str
    filing_date: str
    filing_document_url: str
    item1: str
    item1a: str
    item7: str
    item7a: str
    item8: str
    item16: str
    notes: str

