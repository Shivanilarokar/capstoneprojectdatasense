from __future__ import annotations

import re
from typing import Any

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_QUOTED_ENTITY_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_ENTITY_PATTERNS = [
    re.compile(r"(?i)\bis\s+(.+?)\s+sanctioned\b"),
    re.compile(r"(?i)\bscreen\s+(.+?)(?:\s+for\s+sanctions)?\b"),
    re.compile(r"(?i)\bcheck\s+(.+?)(?:\s+for\s+sanctions)?\b"),
]


def normalize_name(value: str) -> str:
    text = _NON_ALNUM_RE.sub(" ", str(value or "").strip().lower())
    return " ".join(part for part in text.split() if part)


def parse_aliases(raw: str) -> list[str]:
    aliases: list[str] = []
    for alias in re.split(r"[;\n|]+", str(raw or "")):
        cleaned = alias.strip()
        if cleaned and cleaned not in aliases:
            aliases.append(cleaned)
    return aliases


def extract_candidate_entities(question: str) -> list[str]:
    entities: list[str] = []
    for match in _QUOTED_ENTITY_RE.finditer(question):
        for group in match.groups():
            cleaned = str(group or "").strip()
            if cleaned and cleaned not in entities:
                entities.append(cleaned)
    if entities:
        return entities

    for pattern in _ENTITY_PATTERNS:
        matched = pattern.search(question)
        if not matched:
            continue
        candidate = matched.group(1).strip(" ?.,")
        if candidate:
            entities.append(candidate)
            return entities
    return entities


def build_match(entity_name: str, row: dict[str, Any], match_type: str, *, alias_used: str | None = None) -> dict[str, Any]:
    return {
        "entity_name": entity_name,
        "matched_name": row.get("primary_name", ""),
        "match_type": match_type,
        "alias_used": alias_used or "",
        "source_entity_id": row.get("source_entity_id", ""),
        "sanctions_programs": row.get("sanctions_programs", ""),
        "sanctions_type": row.get("sanctions_type", ""),
        "source_file_name": row.get("source_file_name", ""),
    }


def screen_entities(
    question: str,
    rows: list[dict[str, Any]],
    *,
    entity_names: list[str] | None = None,
) -> dict[str, Any]:
    entities = [name for name in (entity_names or extract_candidate_entities(question)) if str(name).strip()]
    matches: list[dict[str, Any]] = []
    matched_entities: set[str] = set()

    for entity_name in entities:
        normalized_entity = normalize_name(entity_name)
        if not normalized_entity:
            continue
        for row in rows:
            primary_name = str(row.get("primary_name", "") or "")
            normalized_primary = normalize_name(primary_name)
            aliases = parse_aliases(str(row.get("aliases", "") or ""))
            normalized_aliases = {normalize_name(alias): alias for alias in aliases}
            if normalized_entity == normalized_primary:
                matches.append(build_match(entity_name, row, "primary_exact"))
                matched_entities.add(entity_name)
                continue
            if normalized_entity in normalized_aliases:
                matches.append(
                    build_match(
                        entity_name,
                        row,
                        "alias_exact",
                        alias_used=normalized_aliases[normalized_entity],
                    )
                )
                matched_entities.add(entity_name)

    unmatched_entities = [entity for entity in entities if entity not in matched_entities]
    return {
        "entities": entities,
        "matches": matches,
        "unmatched_entities": unmatched_entities,
    }

