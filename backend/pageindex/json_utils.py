"""JSON parsing and persistence helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


def parse_json_object(raw: str) -> Dict[str, Any]:
    """Parse JSON object from model output with block fallback."""
    raw = (raw or "").strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        block = re.search(r"\{[\s\S]*\}", raw)
        if not block:
            return {}
        try:
            parsed = json.loads(block.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def parse_json_array(raw: str) -> List[Any]:
    """Parse JSON array and return [] for invalid payloads."""
    raw = (raw or "").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def write_json(path: Path, payload: Any) -> None:
    """Write stable UTF-8 JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")



