from __future__ import annotations

from pydantic import BaseModel, Field


class AdminMetricCard(BaseModel):
    label: str
    value: str


class AdminTenantSummary(BaseModel):
    tenant_key: str
    display_name: str
    status: str
    member_count: int
    pg_database: str | None = None
    neo4j_database: str | None = None


class AdminUserAccessSummary(BaseModel):
    email: str
    display_name: str
    provider_subject: str = ""
    tenant_key: str
    roles: list[str] = Field(default_factory=list)
    status: str
    is_default: bool
    last_login_at: str | None = None


class AdminAccessUpsertRequest(BaseModel):
    display_name: str
    tenant_key: str
    roles: list[str] = Field(default_factory=list)
    status: str = "active"
    is_default: bool = True


class AdminOverviewResponse(BaseModel):
    status: str
    cards: list[AdminMetricCard] = Field(default_factory=list)
    tenants: list[AdminTenantSummary] = Field(default_factory=list)
    users: list[AdminUserAccessSummary] = Field(default_factory=list)
    available_roles: list[str] = Field(default_factory=list)
