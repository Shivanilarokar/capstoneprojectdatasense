from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_QUOTED_ENTITY_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_ENTITY_PATTERNS = [
    re.compile(r"(?i)\bis\s+(.+?)\s+sanctioned\b"),
    re.compile(r"(?i)\bscreen\s+(.+?)(?:\s+for\s+sanctions)?\b"),
    re.compile(r"(?i)\bcheck\s+(.+?)(?:\s+for\s+sanctions)?\b"),
]
_LEGAL_SUFFIX_MAP = {
    "limited": "ltd",
    "ltd": "ltd",
    "incorporated": "inc",
    "inc": "inc",
    "corporation": "corp",
    "corp": "corp",
    "company": "co",
    "co": "co",
}
_COUNTRY_SYNONYMS = {
    "uae": "united arab emirates",
    "u.a.e.": "united arab emirates",
    "united arab emirates": "united arab emirates",
    "usa": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "united states": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "united kingdom": "united kingdom",
    "russia": "russia",
    "china": "china",
    "india": "india",
    "taiwan": "taiwan",
}


def normalize_name(value: str) -> str:
    text = _NON_ALNUM_RE.sub(" ", str(value or "").strip().lower())
    tokens = [_LEGAL_SUFFIX_MAP.get(part, part) for part in text.split() if part]
    return " ".join(tokens)


def _normalize_exact_name(value: str) -> str:
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


def extract_country_hints(question: str) -> list[str]:
    hints: list[str] = []
    q = normalize_name(question)
    for raw, canonical in _COUNTRY_SYNONYMS.items():
        if normalize_name(raw) in q and canonical not in hints:
            hints.append(canonical)
    return hints


def _row_countries(row: dict[str, Any]) -> list[str]:
    merged = " ".join(
        str(row.get(key, "") or "")
        for key in ("nationality", "citizenship", "address_text")
    )
    merged_norm = normalize_name(merged)
    countries: list[str] = []
    for raw, canonical in _COUNTRY_SYNONYMS.items():
        if normalize_name(raw) in merged_norm and canonical not in countries:
            countries.append(canonical)
    return countries


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    seq = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return seq
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return max(seq, jaccard)


def _country_alignment_score(hints: list[str], row_countries: list[str]) -> float:
    if not hints or not row_countries:
        return 0.0
    return 0.1 if set(hints) & set(row_countries) else -0.2


def build_match(
    entity_name: str,
    row: dict[str, Any],
    match_type: str,
    *,
    alias_used: str | None = None,
    score: float = 1.0,
) -> dict[str, Any]:
    return {
        "entity_name": entity_name,
        "matched_name": row.get("primary_name", ""),
        "match_type": match_type,
        "alias_used": alias_used or "",
        "score": round(float(score), 4),
        "source_entity_id": row.get("source_entity_id", ""),
        "sanctions_programs": row.get("sanctions_programs", ""),
        "sanctions_type": row.get("sanctions_type", ""),
        "source_file_name": row.get("source_file_name", ""),
        "countries": _row_countries(row),
        "address_text": row.get("address_text", ""),
    }


def screen_entities(
    question: str,
    rows: list[dict[str, Any]],
    *,
    entity_names: list[str] | None = None,
    country_hints: list[str] | None = None,
) -> dict[str, Any]:
    entities = [name for name in (entity_names or extract_candidate_entities(question)) if str(name).strip()]
    matches: list[dict[str, Any]] = []
    matched_entities: set[str] = set()
    review_candidates: list[dict[str, Any]] = []
    normalized_country_hints = [normalize_name(value) for value in (country_hints or extract_country_hints(question))]

    for entity_name in entities:
        normalized_entity = normalize_name(entity_name)
        exact_entity = _normalize_exact_name(entity_name)
        if not normalized_entity:
            continue
        for row in rows:
            primary_name = str(row.get("primary_name", "") or "")
            normalized_primary = normalize_name(primary_name)
            exact_primary = _normalize_exact_name(primary_name)
            aliases = parse_aliases(str(row.get("aliases", "") or ""))
            normalized_aliases = {normalize_name(alias): alias for alias in aliases}
            exact_aliases = {_normalize_exact_name(alias): alias for alias in aliases}
            row_countries = _row_countries(row)
            if exact_entity == exact_primary:
                matches.append(build_match(entity_name, row, "primary_exact", score=1.0))
                matched_entities.add(entity_name)
                continue
            if exact_entity in exact_aliases:
                matches.append(
                    build_match(
                        entity_name,
                        row,
                        "alias_exact",
                        alias_used=exact_aliases[exact_entity],
                        score=0.99,
                    )
                )
                matched_entities.add(entity_name)
                continue

            candidate_scores = [(normalized_primary, None, "primary_fuzzy")]
            candidate_scores.extend((alias_norm, alias_raw, "alias_fuzzy") for alias_norm, alias_raw in normalized_aliases.items())
            for candidate_norm, alias_raw, match_type in candidate_scores:
                similarity = _similarity(normalized_entity, candidate_norm)
                if similarity < 0.84:
                    continue
                similarity += _country_alignment_score(normalized_country_hints, row_countries)
                if normalized_country_hints and row_countries and not (set(normalized_country_hints) & set(row_countries)):
                    review_candidates.append(
                        {
                            "entity_name": entity_name,
                            "matched_name": primary_name,
                            "alias_used": alias_raw or "",
                            "score": round(max(similarity, 0.0), 4),
                            "reason": "country_conflict",
                            "countries": row_countries,
                            "source_entity_id": row.get("source_entity_id", ""),
                        }
                    )
                    break
                if similarity >= 0.9:
                    matches.append(
                        build_match(
                            entity_name,
                            row,
                            match_type,
                            alias_used=alias_raw,
                            score=min(similarity, 0.98),
                        )
                    )
                    matched_entities.add(entity_name)
                    break

    unmatched_entities = [entity for entity in entities if entity not in matched_entities]
    return {
        "entities": entities,
        "matches": matches,
        "unmatched_entities": unmatched_entities,
        "review_candidates": review_candidates,
    }
