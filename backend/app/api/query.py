from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_settings, require_workspace_access
from backend.app.api.models.query import QueryRequest, QueryResponse
from backend.app.auth.principal import CurrentPrincipal
from backend.app.services.orchestrator_service import ask_supplychainnexus
from backend.config import AppConfig


router = APIRouter(prefix="/query", tags=["query"])


@router.post("/ask", response_model=QueryResponse)
def ask(
    payload: QueryRequest,
    principal: CurrentPrincipal = Depends(require_workspace_access),
    settings: AppConfig = Depends(get_current_settings),
) -> QueryResponse:
    result = ask_supplychainnexus(
        settings=settings,
        question=payload.question,
        user_id=principal.subject,
        roles=principal.roles,
    )
    return QueryResponse.model_validate(result)
