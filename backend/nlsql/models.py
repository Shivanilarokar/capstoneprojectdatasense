from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SqlGenerationResult:
    reasoning: str
    tables: list[str]
    sql: str
    ambiguity: bool = False

    def __post_init__(self) -> None:
        if not self.sql.strip():
            raise ValueError("Generated SQL cannot be blank.")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class QueryExecutionResult:
    sql: str
    rows: list[dict] = field(default_factory=list)
    error: str = ""
    repaired: bool = False


