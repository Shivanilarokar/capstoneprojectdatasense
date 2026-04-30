from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import psycopg
from psycopg.rows import dict_row

from backend.app.tenancy.context import TenantRuntimeContext
from backend.app.control_plane.schema import (
    TENANTS_SQL,
    USER_ROLE_ASSIGNMENTS_SQL,
    USER_TENANT_MEMBERSHIPS_SQL,
    USERS_SQL,
)


@dataclass(frozen=True)
class TenantRecord:
    tenant_key: str
    display_name: str
    status: str
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str
    pg_sslmode: str
    pg_connect_timeout: int
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str

    def to_runtime_context(self) -> TenantRuntimeContext:
        return TenantRuntimeContext(
            tenant_key=self.tenant_key,
            tenant_status=self.status,
            pg_host=self.pg_host,
            pg_port=self.pg_port,
            pg_database=self.pg_database,
            pg_user=self.pg_user,
            pg_password=self.pg_password,
            pg_sslmode=self.pg_sslmode,
            pg_connect_timeout=self.pg_connect_timeout,
            neo4j_uri=self.neo4j_uri,
            neo4j_username=self.neo4j_username,
            neo4j_password=self.neo4j_password,
            neo4j_database=self.neo4j_database,
        )


@dataclass(frozen=True)
class UserAccessRecord:
    email: str
    display_name: str
    provider_subject: str
    tenant_key: str
    roles: tuple[str, ...]
    status: str
    is_default: bool
    last_login_at: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "email": self.email,
            "display_name": self.display_name,
            "provider_subject": self.provider_subject,
            "tenant_key": self.tenant_key,
            "roles": list(self.roles),
            "status": self.status,
            "is_default": self.is_default,
            "last_login_at": self.last_login_at,
        }


@dataclass(frozen=True)
class TenantAccessSummary:
    tenant_key: str
    display_name: str
    status: str
    member_count: int
    pg_database: str | None = None
    neo4j_database: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "tenant_key": self.tenant_key,
            "display_name": self.display_name,
            "status": self.status,
            "member_count": self.member_count,
            "pg_database": self.pg_database,
            "neo4j_database": self.neo4j_database,
        }


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_roles(raw_roles: Iterable[str]) -> tuple[str, ...]:
    roles: list[str] = []
    for value in raw_roles:
        role = str(value or "").strip()
        if role and role not in roles:
            roles.append(role)
    return tuple(roles)


class ControlPlaneRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url.strip()
        if not self.database_url:
            raise ValueError("Control-plane database URL is required.")
        self._is_sqlite = self.database_url.startswith("sqlite:///")

    def ensure_schema(self) -> None:
        statements = (
            TENANTS_SQL,
            USERS_SQL,
            USER_TENANT_MEMBERSHIPS_SQL,
            USER_ROLE_ASSIGNMENTS_SQL,
        )
        with self._connect() as conn:
            if self._is_sqlite:
                for statement in statements:
                    conn.execute(statement)
            else:
                with conn.cursor() as cursor:
                    for statement in statements:
                        cursor.execute(statement)

    def upsert_access_assignment(
        self,
        *,
        email: str,
        display_name: str,
        provider_subject: str,
        tenant_key: str,
        roles: Iterable[str],
        status: str,
        is_default: bool,
    ) -> UserAccessRecord:
        normalized_email = _normalize_email(email)
        normalized_display_name = display_name.strip() or normalized_email
        normalized_subject = provider_subject.strip()
        normalized_tenant_key = tenant_key.strip() or "default"
        normalized_status = status.strip() or "active"
        normalized_roles = _normalize_roles(roles)

        if not normalized_roles:
            raise ValueError("At least one role is required for an access assignment.")

        self.ensure_schema()
        with self._connect() as conn:
            if self._is_sqlite:
                conn.execute(
                    """
                    INSERT INTO users (email, display_name, provider_subject, status, last_login_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(email) DO UPDATE SET
                        display_name = excluded.display_name,
                        provider_subject = CASE
                            WHEN excluded.provider_subject <> '' THEN excluded.provider_subject
                            ELSE users.provider_subject
                        END,
                        status = excluded.status,
                        last_login_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    """.strip(),
                    (
                        normalized_email,
                        normalized_display_name,
                        normalized_subject,
                        normalized_status,
                    ),
                )
                if is_default:
                    conn.execute(
                        "UPDATE user_tenant_memberships SET is_default = 0, updated_at = CURRENT_TIMESTAMP WHERE email = ?",
                        (normalized_email,),
                    )
                conn.execute(
                    """
                    INSERT INTO user_tenant_memberships (email, tenant_key, status, is_default)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(email, tenant_key) DO UPDATE SET
                        status = excluded.status,
                        is_default = excluded.is_default,
                        updated_at = CURRENT_TIMESTAMP
                    """.strip(),
                    (
                        normalized_email,
                        normalized_tenant_key,
                        normalized_status,
                        1 if is_default else 0,
                    ),
                )
                conn.execute(
                    "DELETE FROM user_role_assignments WHERE email = ? AND tenant_key = ?",
                    (normalized_email, normalized_tenant_key),
                )
                conn.executemany(
                    "INSERT INTO user_role_assignments (email, tenant_key, role) VALUES (?, ?, ?)",
                    [(normalized_email, normalized_tenant_key, role) for role in normalized_roles],
                )
            else:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (email, display_name, provider_subject, status, last_login_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT(email) DO UPDATE SET
                            display_name = EXCLUDED.display_name,
                            provider_subject = CASE
                                WHEN EXCLUDED.provider_subject <> '' THEN EXCLUDED.provider_subject
                                ELSE users.provider_subject
                            END,
                            status = EXCLUDED.status,
                            last_login_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        """.strip(),
                        (
                            normalized_email,
                            normalized_display_name,
                            normalized_subject,
                            normalized_status,
                        ),
                    )
                    if is_default:
                        cursor.execute(
                            "UPDATE user_tenant_memberships SET is_default = FALSE, updated_at = CURRENT_TIMESTAMP WHERE email = %s",
                            (normalized_email,),
                        )
                    cursor.execute(
                        """
                        INSERT INTO user_tenant_memberships (email, tenant_key, status, is_default)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(email, tenant_key) DO UPDATE SET
                            status = EXCLUDED.status,
                            is_default = EXCLUDED.is_default,
                            updated_at = CURRENT_TIMESTAMP
                        """.strip(),
                        (
                            normalized_email,
                            normalized_tenant_key,
                            normalized_status,
                            is_default,
                        ),
                    )
                    cursor.execute(
                        "DELETE FROM user_role_assignments WHERE email = %s AND tenant_key = %s",
                        (normalized_email, normalized_tenant_key),
                    )
                    cursor.executemany(
                        "INSERT INTO user_role_assignments (email, tenant_key, role) VALUES (%s, %s, %s)",
                        [(normalized_email, normalized_tenant_key, role) for role in normalized_roles],
                    )

        record = self.resolve_user_access(normalized_email, tenant_key=normalized_tenant_key)
        if record is None:
            raise RuntimeError("Failed to resolve control-plane access assignment after upsert.")
        return record

    def touch_user_identity(self, *, email: str, display_name: str, provider_subject: str) -> None:
        normalized_email = _normalize_email(email)
        normalized_display_name = display_name.strip() or normalized_email
        normalized_subject = provider_subject.strip()
        self.ensure_schema()
        with self._connect() as conn:
            if self._is_sqlite:
                conn.execute(
                    """
                    UPDATE users
                    SET display_name = ?,
                        provider_subject = CASE
                            WHEN ? <> '' THEN ?
                            ELSE provider_subject
                        END,
                        last_login_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = ?
                    """.strip(),
                    (
                        normalized_display_name,
                        normalized_subject,
                        normalized_subject,
                        normalized_email,
                    ),
                )
            else:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET display_name = %s,
                            provider_subject = CASE
                                WHEN %s <> '' THEN %s
                                ELSE provider_subject
                            END,
                            last_login_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE email = %s
                        """.strip(),
                        (
                            normalized_display_name,
                            normalized_subject,
                            normalized_subject,
                            normalized_email,
                        ),
                    )

    def has_access_assignments(self) -> bool:
        self.ensure_schema()
        with self._connect() as conn:
            if self._is_sqlite:
                row = conn.execute(
                    "SELECT COUNT(*) AS count FROM user_tenant_memberships"
                ).fetchone()
                return bool(row["count"])
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS count FROM user_tenant_memberships")
                row = cursor.fetchone()
                return bool((row or {}).get("count"))

    def resolve_user_access(self, email: str, tenant_key: str | None = None) -> UserAccessRecord | None:
        normalized_email = _normalize_email(email)
        normalized_tenant_key = (tenant_key or "").strip()
        self.ensure_schema()
        with self._connect() as conn:
            if self._is_sqlite:
                params: tuple[object, ...]
                query = """
                    SELECT
                        u.email,
                        u.display_name,
                        u.provider_subject,
                        u.last_login_at,
                        m.tenant_key,
                        m.status,
                        m.is_default
                    FROM users u
                    JOIN user_tenant_memberships m ON m.email = u.email
                    WHERE u.email = ?
                """.strip()
                params = (normalized_email,)
                if normalized_tenant_key:
                    query += " AND m.tenant_key = ?"
                    params += (normalized_tenant_key,)
                query += " ORDER BY CASE WHEN m.status = 'active' THEN 0 ELSE 1 END, CASE WHEN m.is_default THEN 0 ELSE 1 END, m.tenant_key LIMIT 1"
                row = conn.execute(query, params).fetchone()
                if row is None:
                    return None
                roles_rows = conn.execute(
                    "SELECT role FROM user_role_assignments WHERE email = ? AND tenant_key = ? ORDER BY role",
                    (normalized_email, row["tenant_key"]),
                ).fetchall()
                roles = tuple(str(role_row["role"]) for role_row in roles_rows)
                return UserAccessRecord(
                    email=str(row["email"]),
                    display_name=str(row["display_name"]),
                    provider_subject=str(row["provider_subject"] or ""),
                    tenant_key=str(row["tenant_key"]),
                    roles=roles,
                    status=str(row["status"]),
                    is_default=bool(row["is_default"]),
                    last_login_at=str(row["last_login_at"]) if row["last_login_at"] else None,
                )

            with conn.cursor() as cursor:
                params = [normalized_email]
                query = """
                    SELECT
                        u.email,
                        u.display_name,
                        u.provider_subject,
                        u.last_login_at,
                        m.tenant_key,
                        m.status,
                        m.is_default
                    FROM users u
                    JOIN user_tenant_memberships m ON m.email = u.email
                    WHERE u.email = %s
                """.strip()
                if normalized_tenant_key:
                    query += " AND m.tenant_key = %s"
                    params.append(normalized_tenant_key)
                query += " ORDER BY CASE WHEN m.status = 'active' THEN 0 ELSE 1 END, CASE WHEN m.is_default THEN 0 ELSE 1 END, m.tenant_key LIMIT 1"
                cursor.execute(query, params)
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    "SELECT role FROM user_role_assignments WHERE email = %s AND tenant_key = %s ORDER BY role",
                    (normalized_email, row["tenant_key"]),
                )
                roles_rows = cursor.fetchall()
                roles = tuple(str(role_row["role"]) for role_row in roles_rows)
                return UserAccessRecord(
                    email=str(row["email"]),
                    display_name=str(row["display_name"]),
                    provider_subject=str(row["provider_subject"] or ""),
                    tenant_key=str(row["tenant_key"]),
                    roles=roles,
                    status=str(row["status"]),
                    is_default=bool(row["is_default"]),
                    last_login_at=str(row["last_login_at"]) if row["last_login_at"] else None,
                )

    def list_access_assignments(self) -> list[UserAccessRecord]:
        self.ensure_schema()
        with self._connect() as conn:
            if self._is_sqlite:
                assignments = conn.execute(
                    """
                    SELECT
                        u.email,
                        u.display_name,
                        u.provider_subject,
                        u.last_login_at,
                        m.tenant_key,
                        m.status,
                        m.is_default
                    FROM users u
                    JOIN user_tenant_memberships m ON m.email = u.email
                    ORDER BY u.email, CASE WHEN m.is_default THEN 0 ELSE 1 END, m.tenant_key
                    """.strip()
                ).fetchall()
                roles_rows = conn.execute(
                    "SELECT email, tenant_key, role FROM user_role_assignments ORDER BY email, tenant_key, role"
                ).fetchall()
            else:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            u.email,
                            u.display_name,
                            u.provider_subject,
                            u.last_login_at,
                            m.tenant_key,
                            m.status,
                            m.is_default
                        FROM users u
                        JOIN user_tenant_memberships m ON m.email = u.email
                        ORDER BY u.email, CASE WHEN m.is_default THEN 0 ELSE 1 END, m.tenant_key
                        """.strip()
                    )
                    assignments = cursor.fetchall()
                    cursor.execute(
                        "SELECT email, tenant_key, role FROM user_role_assignments ORDER BY email, tenant_key, role"
                    )
                    roles_rows = cursor.fetchall()

        roles_map: dict[tuple[str, str], list[str]] = {}
        for row in roles_rows:
            key = (str(row["email"]), str(row["tenant_key"]))
            roles_map.setdefault(key, []).append(str(row["role"]))

        results: list[UserAccessRecord] = []
        for row in assignments:
            key = (str(row["email"]), str(row["tenant_key"]))
            results.append(
                UserAccessRecord(
                    email=str(row["email"]),
                    display_name=str(row["display_name"]),
                    provider_subject=str(row["provider_subject"] or ""),
                    tenant_key=str(row["tenant_key"]),
                    roles=tuple(roles_map.get(key, [])),
                    status=str(row["status"]),
                    is_default=bool(row["is_default"]),
                    last_login_at=str(row["last_login_at"]) if row["last_login_at"] else None,
                )
            )
        return results

    def list_tenant_access_summaries(self) -> list[TenantAccessSummary]:
        self.ensure_schema()
        with self._connect() as conn:
            if self._is_sqlite:
                tenant_rows = conn.execute(
                    "SELECT tenant_key, display_name, status, pg_database, neo4j_database FROM tenants ORDER BY tenant_key"
                ).fetchall()
                membership_rows = conn.execute(
                    """
                    SELECT tenant_key, status, COUNT(DISTINCT email) AS member_count
                    FROM user_tenant_memberships
                    GROUP BY tenant_key, status
                    ORDER BY tenant_key
                    """.strip()
                ).fetchall()
            else:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT tenant_key, display_name, status, pg_database, neo4j_database FROM tenants ORDER BY tenant_key"
                    )
                    tenant_rows = cursor.fetchall()
                    cursor.execute(
                        """
                        SELECT tenant_key, status, COUNT(DISTINCT email) AS member_count
                        FROM user_tenant_memberships
                        GROUP BY tenant_key, status
                        ORDER BY tenant_key
                        """.strip()
                    )
                    membership_rows = cursor.fetchall()

        tenant_map = {
            str(row["tenant_key"]): {
                "display_name": str(row["display_name"]),
                "status": str(row["status"]),
                "pg_database": str(row["pg_database"]) if row["pg_database"] else None,
                "neo4j_database": str(row["neo4j_database"]) if row["neo4j_database"] else None,
            }
            for row in tenant_rows
        }
        summaries: list[TenantAccessSummary] = []
        seen: set[str] = set()
        for row in membership_rows:
            tenant_key = str(row["tenant_key"])
            tenant_info = tenant_map.get(tenant_key, {})
            summaries.append(
                TenantAccessSummary(
                    tenant_key=tenant_key,
                    display_name=str(tenant_info.get("display_name") or tenant_key),
                    status=str(tenant_info.get("status") or row["status"]),
                    member_count=int(row["member_count"]),
                    pg_database=tenant_info.get("pg_database"),
                    neo4j_database=tenant_info.get("neo4j_database"),
                )
            )
            seen.add(tenant_key)
        for tenant_key, tenant_info in tenant_map.items():
            if tenant_key in seen:
                continue
            summaries.append(
                TenantAccessSummary(
                    tenant_key=tenant_key,
                    display_name=str(tenant_info.get("display_name") or tenant_key),
                    status=str(tenant_info.get("status") or "unknown"),
                    member_count=0,
                    pg_database=tenant_info.get("pg_database"),
                    neo4j_database=tenant_info.get("neo4j_database"),
                )
            )
        return sorted(summaries, key=lambda item: item.tenant_key)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection | psycopg.Connection]:
        if self._is_sqlite:
            database_path = Path(self.database_url.removeprefix("sqlite:///"))
            database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
            return

        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
