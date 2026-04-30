"""Neo4j client wrapper for graph retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

from backend.config import AppConfig


@dataclass
class Neo4jStore:
    """Thin wrapper around Neo4j driver with batched write helpers."""

    settings: AppConfig

    def __post_init__(self) -> None:
        if not self.settings.neo4j_password:
            raise RuntimeError("NEO4J_PASSWORD is required for Graph RAG query.")
        driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_username, self.settings.neo4j_password),
        )
        try:
            driver.verify_connectivity()
        except AuthError as exc:
            driver.close()
            raise RuntimeError(
                "Neo4j authentication failed. Check NEO4J_USERNAME and NEO4J_PASSWORD in .env "
                "or reset the Aura database password."
            ) from exc
        except ServiceUnavailable as exc:
            driver.close()
            raise RuntimeError(
                f"Neo4j network path is not reachable for {self.settings.neo4j_uri}. "
                "Check NEO4J_URI, local firewall, and whether the current network allows Bolt access. "
                f"Original error: {exc}"
            ) from exc
        except Neo4jError as exc:
            driver.close()
            raise RuntimeError(f"Neo4j connection failed: {exc}") from exc
        self._driver = driver

    def close(self) -> None:
        """Close underlying driver."""
        self._driver.close()

    def execute_write(self, cypher: str, parameters: dict[str, Any] | None = None) -> None:
        """Execute write transaction."""
        with self._driver.session(database=self.settings.neo4j_database) as session:
            session.execute_write(lambda tx: tx.run(cypher, parameters or {}).consume())

    def execute_read(self, cypher: str, parameters: dict[str, Any] | None = None) -> List[dict[str, Any]]:
        """Execute read transaction and return list of dicts."""
        with self._driver.session(database=self.settings.neo4j_database) as session:
            result = session.execute_read(lambda tx: list(tx.run(cypher, parameters or {})))
        return [record.data() for record in result]

    def execute_write_return(self, cypher: str, parameters: dict[str, Any] | None = None) -> List[dict[str, Any]]:
        """Execute write transaction and return result rows."""
        with self._driver.session(database=self.settings.neo4j_database) as session:
            result = session.execute_write(lambda tx: [record.data() for record in tx.run(cypher, parameters or {})])
        return result

    def write_rows(
        self,
        cypher: str,
        rows: Iterable[dict[str, Any]],
        tenant_id: str,
        batch_size: int = 500,
    ) -> int:
        """Write rows in batches using UNWIND query pattern."""
        total = 0
        batch: list[dict[str, Any]] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                self.execute_write(cypher, {"rows": batch, "tenant_id": tenant_id})
                total += len(batch)
                batch = []
        if batch:
            self.execute_write(cypher, {"rows": batch, "tenant_id": tenant_id})
            total += len(batch)
        return total


