from __future__ import annotations

from pydantic import BaseModel


class CurrentPrincipalResponse(BaseModel):
    subject: str
    email: str
    roles: list[str]
    tenant_key: str
