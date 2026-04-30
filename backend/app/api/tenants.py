from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import require_workspace_access
from backend.app.api.models.tenant import TenantSummaryResponse
from backend.app.auth.principal import CurrentPrincipal


router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantSummaryResponse)
def current_tenant(principal: CurrentPrincipal = Depends(require_workspace_access)) -> TenantSummaryResponse:
    return TenantSummaryResponse(tenant_key=principal.tenant_key, status="active")
