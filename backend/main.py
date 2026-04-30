from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.auth import router as auth_router
from backend.app.api.admin import router as admin_router
from backend.app.api.query import router as query_router
from backend.app.api.system import router as system_router
from backend.app.api.tenants import router as tenants_router
from backend.config import load_app_config


def create_app() -> FastAPI:
    settings = load_app_config()
    app = FastAPI(title="SupplyChainNexus API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(query_router)
    app.include_router(system_router)
    app.include_router(tenants_router)
    return app


app = create_app()
