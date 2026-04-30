from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import require_admin
from backend.app.api.models.admin import AdminAccessUpsertRequest, AdminOverviewResponse, AdminUserAccessSummary
from backend.app.auth.principal import CurrentPrincipal
from backend.app.services.admin_service import build_admin_overview_snapshot, save_admin_access_assignment


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewResponse)
def overview(principal: CurrentPrincipal = Depends(require_admin)) -> AdminOverviewResponse:
    _ = principal
    return AdminOverviewResponse.model_validate(build_admin_overview_snapshot())


@router.put("/access/{email}", response_model=AdminUserAccessSummary)
def upsert_access(
    email: str,
    payload: AdminAccessUpsertRequest,
    principal: CurrentPrincipal = Depends(require_admin),
) -> AdminUserAccessSummary:
    _ = principal
    return AdminUserAccessSummary.model_validate(
        save_admin_access_assignment(
            email=email,
            display_name=payload.display_name,
            tenant_key=payload.tenant_key,
            roles=payload.roles,
            status_value=payload.status,
            is_default=payload.is_default,
        )
    )
