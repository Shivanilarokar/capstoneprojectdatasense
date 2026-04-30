from __future__ import annotations

import hashlib
import json
from typing import Iterable, Iterator, Sequence


def stable_record_hash(*parts: object) -> str:
    payload = "||".join("" if part is None else str(part).strip() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def json_payload(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, default=str)


def batched(iterable: Iterable[dict], size: int = 1000) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def build_upsert_statement(
    table_name: str,
    columns: Sequence[str],
    conflict_columns: Sequence[str],
) -> str:
    insert_columns = ", ".join(columns)
    placeholders = ", ".join(f"%({column})s" for column in columns)
    update_columns = [column for column in columns if column not in conflict_columns]
    if update_columns:
        update_clause = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
        conflict_action = f"DO UPDATE SET {update_clause}"
    else:
        conflict_action = "DO NOTHING"
    conflict_list = ", ".join(conflict_columns)
    return (
        f"INSERT INTO {table_name} ({insert_columns}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_list}) {conflict_action}"
    )


