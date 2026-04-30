from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.models.system import SystemStatusResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=SystemStatusResponse)
def health() -> SystemStatusResponse:
    return SystemStatusResponse(status="ok")
