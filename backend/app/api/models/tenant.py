from __future__ import annotations

from pydantic import BaseModel


class TenantSummaryResponse(BaseModel):
    tenant_key: str
    status: str
