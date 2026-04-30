"""Shared utility helpers for Graph RAG."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Iterable, List


_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
_MULTISPACE_RE = re.compile(r"\s+")

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
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


def normalize_name(value: str) -> str:
    """Normalize entity names for deterministic matching."""
    if not value:
        return ""
    upper = value.upper().strip()
    upper = upper.replace("&", " AND ")
    cleaned = _NON_ALNUM_RE.sub(" ", upper)
    return _MULTISPACE_RE.sub(" ", cleaned).strip()


def stable_id(*parts: str, prefix: str = "") -> str:
    """Build stable ID from a set of string parts."""
    payload = "||".join((p or "").strip() for p in parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:20]}"


def parse_iso_date(raw: str | None) -> str | None:
    """Parse best-effort date into YYYY-MM-DD; returns None if parsing fails."""
    if not raw:
        return None
    value = str(raw).strip()
    if not value:
        return None

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%Y%m%d",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def filing_quarter(date_iso: str | None) -> int | None:
    """Convert YYYY-MM-DD date to quarter number."""
    if not date_iso:
        return None
    try:
        month = int(date_iso.split("-")[1])
    except (ValueError, IndexError):
        return None
    return ((month - 1) // 3) + 1


def safe_float(value: object) -> float | None:
    """Parse float safely and return None for empty/invalid values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_damage_amount(raw: object) -> float | None:
    """Parse NOAA damage amount values like 10K, 2.5M, 1B."""
    if raw is None:
        return None
    text = str(raw).strip().upper()
    if not text:
        return None
    multiplier = 1.0
    if text.endswith("K"):
        multiplier = 1_000.0
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000.0
        text = text[:-1]
    elif text.endswith("B"):
        multiplier = 1_000_000_000.0
        text = text[:-1]
    number = safe_float(text)
    if number is None:
        return None
    return number * multiplier


def split_semicolon_values(raw: str | None) -> List[str]:
    """Split semicolon-delimited field into clean unique values."""
    if not raw:
        return []
    values: List[str] = []
    for part in str(raw).split(";"):
        value = part.strip()
        if not value:
            continue
        if value not in values:
            values.append(value)
    return values


def tokenize_terms(question: str, min_len: int = 3) -> List[str]:
    """Extract query terms for route-level lexical filtering."""
    tokens = re.findall(r"[A-Za-z0-9]{2,}", (question or "").lower())
    out: List[str] = []
    for token in tokens:
        if len(token) < min_len or token in STOPWORDS:
            continue
        if token not in out:
            out.append(token)
    return out


def limit_rows(rows: Iterable[dict], limit: int | None) -> List[dict]:
    """Materialize iterable rows with an optional cap."""
    out: List[dict] = []
    for row in rows:
        out.append(row)
        if limit is not None and len(out) >= limit:
            break
    return out



