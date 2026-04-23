from __future__ import annotations

import csv
from pathlib import Path

from .base import json_payload


TABLE_NAME = "source_noaa_storm_events"
CONFLICT_COLUMNS = ("tenant_id", "event_id")


def parse_damage_value(value: str) -> float:
    raw = (value or "").strip().upper()
    if not raw or raw == "0":
        return 0.0
    multiplier = 1.0
    if raw.endswith("K"):
        multiplier = 1_000.0
        raw = raw[:-1]
    elif raw.endswith("M"):
        multiplier = 1_000_000.0
        raw = raw[:-1]
    elif raw.endswith("B"):
        multiplier = 1_000_000_000.0
        raw = raw[:-1]
    return float(raw) * multiplier


def transform_noaa_row(tenant_id: str, source_file_name: str, row: dict) -> dict:
    return {
        "tenant_id": tenant_id,
        "event_id": int(row["EVENT_ID"]),
        "episode_id": int(row["EPISODE_ID"]) if str(row.get("EPISODE_ID", "") or "").strip() else None,
        "state": str(row.get("STATE", "") or "").strip(),
        "year": int(row["YEAR"]) if str(row.get("YEAR", "") or "").strip() else None,
        "month_name": str(row.get("MONTH_NAME", "") or "").strip(),
        "event_type": str(row.get("EVENT_TYPE", "") or "").strip(),
        "cz_name": str(row.get("CZ_NAME", "") or "").strip(),
        "begin_date_time": str(row.get("BEGIN_DATE_TIME", "") or "").strip(),
        "end_date_time": str(row.get("END_DATE_TIME", "") or "").strip(),
        "damage_property_raw": str(row.get("DAMAGE_PROPERTY", "") or "").strip(),
        "damage_property_usd": parse_damage_value(str(row.get("DAMAGE_PROPERTY", "") or "")),
        "damage_crops_raw": str(row.get("DAMAGE_CROPS", "") or "").strip(),
        "damage_crops_usd": parse_damage_value(str(row.get("DAMAGE_CROPS", "") or "")),
        "begin_lat": float(row["BEGIN_LAT"]) if str(row.get("BEGIN_LAT", "") or "").strip() else None,
        "begin_lon": float(row["BEGIN_LON"]) if str(row.get("BEGIN_LON", "") or "").strip() else None,
        "end_lat": float(row["END_LAT"]) if str(row.get("END_LAT", "") or "").strip() else None,
        "end_lon": float(row["END_LON"]) if str(row.get("END_LON", "") or "").strip() else None,
        "episode_narrative": str(row.get("EPISODE_NARRATIVE", "") or "").strip(),
        "event_narrative": str(row.get("EVENT_NARRATIVE", "") or "").strip(),
        "source_file_name": source_file_name,
        "raw_payload": json_payload(row),
    }


def iter_noaa_records(tenant_id: str, source_path: Path):
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not str(row.get("EVENT_ID", "") or "").strip():
                continue
            yield transform_noaa_row(tenant_id, source_path.name, row)
