from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .base import json_payload


TABLE_NAME = "source_noaa_storm_events"
CONFLICT_COLUMNS = ("tenant_id", "event_id")


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_int(value: object) -> int | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _parse_float(value: object) -> float | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


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


def midpoint_coordinate(begin_value: object, end_value: object) -> float | None:
    begin = _parse_float(begin_value)
    end = _parse_float(end_value)
    if begin is None and end is None:
        return None
    if begin is None:
        return end
    if end is None:
        return begin
    return round((begin + end) / 2.0, 6)


def parse_noaa_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, "%d-%b-%y %H:%M:%S")
    except ValueError:
        return None
    if parsed.year > datetime.now().year + 1:
        return parsed.replace(year=parsed.year - 100)
    return parsed


def transform_noaa_row(tenant_id: str, source_file_name: str, row: dict) -> dict:
    return {
        "tenant_id": tenant_id,
        "begin_yearmonth": _parse_int(row.get("BEGIN_YEARMONTH")),
        "begin_day": _parse_int(row.get("BEGIN_DAY")),
        "begin_time": _parse_int(row.get("BEGIN_TIME")),
        "end_yearmonth": _parse_int(row.get("END_YEARMONTH")),
        "end_day": _parse_int(row.get("END_DAY")),
        "end_time": _parse_int(row.get("END_TIME")),
        "episode_id": _parse_int(row.get("EPISODE_ID")),
        "event_id": int(row["EVENT_ID"]),
        "state": _clean_text(row.get("STATE")),
        "state_fips": _parse_int(row.get("STATE_FIPS")),
        "year": _parse_int(row.get("YEAR")),
        "month_name": _clean_text(row.get("MONTH_NAME")),
        "event_type": _clean_text(row.get("EVENT_TYPE")),
        "cz_type": _clean_text(row.get("CZ_TYPE")),
        "cz_fips": _parse_int(row.get("CZ_FIPS")),
        "cz_name": _clean_text(row.get("CZ_NAME")),
        "wfo": _clean_text(row.get("WFO")),
        "begin_date_time": parse_noaa_timestamp(row.get("BEGIN_DATE_TIME")),
        "cz_timezone": _clean_text(row.get("CZ_TIMEZONE")),
        "end_date_time": parse_noaa_timestamp(row.get("END_DATE_TIME")),
        "injuries_direct": _parse_int(row.get("INJURIES_DIRECT")),
        "injuries_indirect": _parse_int(row.get("INJURIES_INDIRECT")),
        "deaths_direct": _parse_int(row.get("DEATHS_DIRECT")),
        "deaths_indirect": _parse_int(row.get("DEATHS_INDIRECT")),
        "damage_property_raw": _clean_text(row.get("DAMAGE_PROPERTY")),
        "damage_property_usd": parse_damage_value(_clean_text(row.get("DAMAGE_PROPERTY"))),
        "damage_crops_raw": _clean_text(row.get("DAMAGE_CROPS")),
        "damage_crops_usd": parse_damage_value(_clean_text(row.get("DAMAGE_CROPS"))),
        "source": _clean_text(row.get("SOURCE")),
        "magnitude": _parse_float(row.get("MAGNITUDE")),
        "magnitude_type": _clean_text(row.get("MAGNITUDE_TYPE")),
        "flood_cause": _clean_text(row.get("FLOOD_CAUSE")),
        "category": _clean_text(row.get("CATEGORY")),
        "tor_f_scale": _clean_text(row.get("TOR_F_SCALE")),
        "tor_length": _parse_float(row.get("TOR_LENGTH")),
        "tor_width": _parse_float(row.get("TOR_WIDTH")),
        "tor_other_wfo": _clean_text(row.get("TOR_OTHER_WFO")),
        "tor_other_cz_state": _clean_text(row.get("TOR_OTHER_CZ_STATE")),
        "tor_other_cz_fips": _parse_int(row.get("TOR_OTHER_CZ_FIPS")),
        "tor_other_cz_name": _clean_text(row.get("TOR_OTHER_CZ_NAME")),
        "begin_range": _parse_float(row.get("BEGIN_RANGE")),
        "begin_azimuth": _clean_text(row.get("BEGIN_AZIMUTH")),
        "begin_location": _clean_text(row.get("BEGIN_LOCATION")),
        "end_range": _parse_float(row.get("END_RANGE")),
        "end_azimuth": _clean_text(row.get("END_AZIMUTH")),
        "end_location": _clean_text(row.get("END_LOCATION")),
        "begin_lat": _parse_float(row.get("BEGIN_LAT")),
        "begin_lon": _parse_float(row.get("BEGIN_LON")),
        "end_lat": _parse_float(row.get("END_LAT")),
        "end_lon": _parse_float(row.get("END_LON")),
        "event_mid_lat": midpoint_coordinate(row.get("BEGIN_LAT"), row.get("END_LAT")),
        "event_mid_lon": midpoint_coordinate(row.get("BEGIN_LON"), row.get("END_LON")),
        "episode_narrative": _clean_text(row.get("EPISODE_NARRATIVE")),
        "event_narrative": _clean_text(row.get("EVENT_NARRATIVE")),
        "data_source": _clean_text(row.get("DATA_SOURCE")),
        "source_file_name": source_file_name,
        "raw_payload": json_payload(row),
    }


def iter_noaa_records(tenant_id: str, source_path: Path):
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not str(row.get("EVENT_ID", "") or "").strip():
                continue
            yield transform_noaa_row(tenant_id, source_path.name, row)


