from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AppConfig
from nlsql.db import connect_postgres

from .matcher import screen_entities

FETCH_SANCTIONS_ROWS_SQL = """
SELECT
    source_entity_id,
    primary_name,
    entity_type,
    sanctions_programs,
    sanctions_type,
    aliases,
    nationality,
    citizenship,
    address_text,
    document_ids,
    date_published,
    source_file_name,
    source_loaded_at
FROM source_ofac_bis_entities
WHERE tenant_id = %(tenant_id)s
ORDER BY primary_name
""".strip()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _latest_loaded_at(rows: list[dict[str, Any]]) -> str | None:
    latest: str | None = None
    for row in rows:
        value = row.get("source_loaded_at")
        if value is None:
            continue
        rendered = str(value)
        if latest is None or rendered > latest:
            latest = rendered
    return latest


def _build_answer(result: dict[str, Any], warnings: list[str]) -> str:
    entities = result["entities"]
    matches = result["matches"]
    unmatched_entities = result["unmatched_entities"]
    review_candidates = result.get("review_candidates", [])

    if matches:
        fragments = []
        for match in matches[:5]:
            qualifier = f" via alias `{match['alias_used']}`" if match.get("alias_used") else ""
            program = match.get("sanctions_programs") or "unspecified program"
            fragments.append(
                f"{match['entity_name']} matched {match['matched_name']} ({match['match_type']}{qualifier}, {program}, score={match.get('score', 1.0):.2f})"
            )
        return "Sanctions screening found matches: " + "; ".join(fragments) + "."

    if review_candidates:
        candidate = review_candidates[0]
        return (
            "Sanctions screening found an ambiguous candidate that needs analyst review: "
            f"{candidate['entity_name']} vs {candidate['matched_name']} "
            f"({candidate['reason']}, score={candidate.get('score', 0.0):.2f})."
        )

    if entities:
        return f"No sanctions matches were found for: {', '.join(entities)}."

    if warnings:
        return warnings[0]
    return "Sanctions screening returned no match information."


def run_sanctions_query(
    settings: AppConfig,
    question: str,
    *,
    entity_names: list[str] | None = None,
    user_id: str = "system",
) -> dict[str, Any]:
    with connect_postgres(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(FETCH_SANCTIONS_ROWS_SQL, {"tenant_id": settings.graph_tenant_id})
            rows = list(cur.fetchall())

    result = screen_entities(question, rows, entity_names=entity_names)
    warnings: list[str] = []
    if not result["entities"]:
        warnings.append("No entity names were extracted from the question for sanctions screening.")

    provenance = {
        "source_table": "source_ofac_bis_entities",
        "source_files": sorted({row.get("source_file_name", "") for row in rows if row.get("source_file_name")}),
        "matched_entity_ids": [match["source_entity_id"] for match in result["matches"]],
        "review_entity_ids": [candidate["source_entity_id"] for candidate in result.get("review_candidates", [])],
    }
    freshness = {
        "latest_loaded_at": _latest_loaded_at(rows),
        "note": "Results reflect the latest ingested OFAC/BIS entity dataset for the selected tenant.",
    }
    debug = {
        "candidate_row_count": len(rows),
        "match_count": len(result["matches"]),
        "user_id": user_id,
    }
    answer = _build_answer(result, warnings)

    audit_payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tenant_id": settings.graph_tenant_id,
        "user_id": user_id,
        "question": question,
        "entities": result["entities"],
        "match_count": len(result["matches"]),
        "review_count": len(result.get("review_candidates", [])),
        "unmatched_entities": result["unmatched_entities"],
    }
    _append_jsonl(settings.sanctions_audit_log, audit_payload)

    return {
        "status": "ok",
        "question": question,
        "route": "sanctions",
        "tenant_id": settings.graph_tenant_id,
        "answer": answer,
        "evidence": result,
        "provenance": provenance,
        "freshness": freshness,
        "warnings": warnings,
        "debug": debug,
    }
