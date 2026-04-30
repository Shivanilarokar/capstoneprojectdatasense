from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _base_event(event_type: str, correlation_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        **(payload or {}),
    }


def emit_trace_event(path: Path, event_type: str, correlation_id: str, payload: dict[str, Any] | None = None) -> None:
    append_jsonl(path, _base_event(event_type, correlation_id, payload))


def emit_alert_event(path: Path, event_type: str, correlation_id: str, payload: dict[str, Any] | None = None) -> None:
    append_jsonl(path, _base_event(event_type, correlation_id, payload))


def write_checkpoint(path: Path, node_name: str, state_snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "node": node_name,
        "state": state_snapshot,
    }
    append_jsonl(path, payload)
    return payload


